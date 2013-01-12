import matplotlib
matplotlib.use('Agg')
import pylab
import numpy as np
import simulation_parameters
from NeuroTools import signals as nts
from NeuroTools import parameters as ntp
import utils

class WeightPlotter(object):
    """
    Class offering several plotting functions.
    The core data file is a file containing cell_gids and spike times.
    """

    def __init__(self, param_fn=None, spiketimes_fn=None):
        """
        params : dictionary or NeuroTools.parameters ParameterSet
        """
        if params == None:
            self.network_params = simulation_parameters.parameter_storage()  # network_params class containing the simulation parameters
            self.params = self.network_params.load_params()                       # params stores cell numbers, etc as a dictionary
        else:
            self.params = params
        self.no_spikes = False

        self.n_fig_x = 2
        self.n_fig_y = 2

        self.n_cells = self.params['n_exc']
        self.nspikes = np.zeros(self.n_cells)                                   # summed activity
        self.spiketrains = [[] for i in xrange(self.n_cells)]
        self.load_spiketimes(data_fn)

    def load_cell_properties(self):
        # sort the cells by their tuning vx, vy properties
        self.tuning_prop = np.loadtxt(self.params['tuning_prop_means_fn'])

        # vx
        self.vx_tuning = self.tuning_prop[:, 2].copy()
        self.vx_tuning.sort()
        self.sorted_indices_vx = self.tuning_prop[:, 2].argsort()
        # vy
        self.vy_tuning = self.tuning_prop[:, 3].copy()
        self.vy_tuning.sort()
        self.sorted_indices_vy = self.tuning_prop[:, 3].argsort()

        self.load_spiketimes(sim_cnt)
        if self.no_spikes:
            return
        fig_width_pt = 800.0  # Get this from LaTeX using \showthe\columnwidth
        inches_per_pt = 1.0/72.27               # Convert pt to inch
        golden_mean = (np.sqrt(5)-1.0)/2.0         # Aesthetic ratio
        fig_width = fig_width_pt*inches_per_pt  # width in inches
        fig_height = fig_width*golden_mean      # height in inches
        fig_size =  [fig_width,fig_height]
        params = {#'backend': 'png',
#                  'axes.labelsize': 10,
#                  'text.fontsize': 10,
#                  'legend.fontsize': 10,
#                  'xtick.labelsize': 8,
#                  'ytick.labelsize': 8,
#                  'text.usetex': True,
                  'figure.figsize': fig_size}
        pylab.rcParams.update(params)


    def load_spiketimes(self, fn):
        """
        Fills the following arrays with data:
        self.nspikes = np.zeros(self.n_cells)                                   # summed activity
        self.nspikes_binned = np.zeros((self.n_cells, self.n_bins))             # binned activity over time
        self.nspikes_binned_normalized = np.zeros((self.n_cells, self.n_bins))  # normalized so that for each bin, the sum of the population activity = 1
        self.nspikes_normalized = np.zeros(self.n_cells)                        # activity normalized, so that sum = 1
        self.nspikes_normalized_nonlinear
        """

        print(' Loading data .... ')
#        folder = self.params['spiketimes_folder']
#        fn = self.params['exc_spiketimes_fn_merged'].rsplit(folder)[1] + '%d.dat' % (sim_cnt)
        
        # NeuroTools
#        spklist = nts.load_spikelist(fn)
#        spiketrains = spklist.spiketrains
        try:
            d = np.loadtxt(fn)
            spiketrains = [[] for i in xrange(self.n_cells)]
            for i in xrange(d[:, 0].size):
                spiketrains[int(d[i, 1])].append(d[i, 0])
        except:
            print 'WARNING: no spikes found in:', fn
            self.no_spikes = True
            return

        for gid in xrange(self.params['n_exc']):
#            spiketimes = spiketrains[gid+1.].spike_times
#            nspikes = spiketimes.size

            spiketimes = spiketrains[gid]
            nspikes = len(spiketimes)
            if (nspikes > 0):
                count, bins = np.histogram(spiketimes, bins=self.n_bins)
                self.nspikes_binned[gid, :] = count
            self.nspikes[gid] = nspikes

        # normalization
        for i in xrange(int(self.n_bins)):
            if (self.nspikes_binned[:, i].sum() > 0):
                self.nspikes_binned_normalized[:, i] = self.nspikes_binned[:, i] / self.nspikes_binned[:,i].sum()
        self.nspikes_normalized = self.nspikes / self.nspikes.sum()

        # activity normalized, nonlinear
        nspikes_shifted = self.nspikes - self.nspikes.max()
        nspikes_exp = np.exp(nspikes_shifted)
        self.nspikes_normalized_nonlinear = nspikes_exp / nspikes_exp.sum()

    def compute_v_estimates(self):
        """
        This function combines activity on the population level to estimate vx, vy

         On which time scale shall the prediction work?
         There are (at least) 3 different ways to do it:
           Very short time-scale:
           1) Compute the prediction for each time bin - based on the activitiy in the respective time bin 
           Short time-scale:
           2) Compute the prediction for each time bin based on all activity in the past
           3) Non-linear 'voting' based on 1)
           Long time-scale:
           3) Compute the prediction based on the the activity of the whole run - not time dependent
           4) Non-linear 'voting' based on 3) 
        """
        # momentary result, based on the activity in one time bin
        self.vx_avg = np.zeros(self.n_bins) 
        self.vy_avg = np.zeros(self.n_bins)
        # ---> gives theta_avg 

        # based on the activity in several time bins
        self.vx_moving_avg = np.zeros((self.n_bins, 2))
        self.vy_moving_avg = np.zeros((self.n_bins, 2))

        # non linear transformation of vx_avg
        self.vx_non_linear = np.zeros(self.n_bins)
        self.vy_non_linear = np.zeros(self.n_bins)

        trace_length = 100 # [ms] window length for moving average 
        trace_length_in_bins = int(round(trace_length / self.time_binsize))
        # ---> gives theta_moving_avg

        # # # # # # # # # # # # # # # # # # # # # # 
        # S P E E D    P R E D I C T I O N 
        # # # # # # # # # # # # # # # # # # # # # # 
        self.vx_confidence_binned = self.nspikes_binned_normalized[self.sorted_indices_vx]
        self.vy_confidence_binned = self.nspikes_binned_normalized[self.sorted_indices_vy]
        vx_prediction_trace = np.zeros((self.n_cells, self.n_bins, 2))    # _trace: prediction based on the momentary and past activity (moving average, and std) --> trace_length
        vy_prediction_trace = np.zeros((self.n_cells, self.n_bins, 2))    # _trace: prediction based on the momentary and past activity (moving average, and std) --> trace_length
        for i in xrange(self.n_bins):

            # 1) momentary vote
            # take the weighted average for v_prediction (weight = normalized activity)
            vx_pred = self.vx_confidence_binned[:, i] * self.vx_tuning
            vy_pred = self.vy_confidence_binned[:, i] * self.vy_tuning
            self.vx_avg[i] = np.sum(vx_pred)
            self.vy_avg[i] = np.sum(vy_pred)

            # 2) moving average
            past_bin = max(0, min(0, i-trace_length_in_bins))
            for cell in xrange(self.n_cells):
                vx_prediction_trace[cell, i, 0] = self.vx_confidence_binned[cell, past_bin:i].mean()
                vx_prediction_trace[cell, i, 1] = self.vx_confidence_binned[cell, past_bin:i].std()
                vy_prediction_trace[cell, i, 0] = self.vy_confidence_binned[cell, past_bin:i].mean()
                vy_prediction_trace[cell, i, 1] = self.vy_confidence_binned[cell, past_bin:i].std()
            self.vx_moving_avg[i, 0] = np.sum(vx_prediction_trace[:, i, 0] * self.vx_tuning)
            self.vx_moving_avg[i, 1] = np.std(vx_prediction_trace[:, i, 1] * self.vx_tuning)
            self.vy_moving_avg[i, 0] = np.sum(vy_prediction_trace[:, i, 0] * self.vy_tuning)
            self.vy_moving_avg[i, 1] = np.std(vy_prediction_trace[:, i, 1] * self.vy_tuning)

            # 3)
            # rescale activity to negative values
            vx_shifted = self.nspikes_binned[self.sorted_indices_vx, i] - self.nspikes_binned[self.sorted_indices_vx, i].max()
            vy_shifted = self.nspikes_binned[self.sorted_indices_vy, i] - self.nspikes_binned[self.sorted_indices_vy, i].max()
            # exp --> mapping to range(0, 1)
            vx_exp = np.exp(vx_shifted)
            vy_exp = np.exp(vy_shifted)
            # normalize and vote
            vx_votes = (vx_exp / vx_exp.sum()) * self.vx_tuning
            vy_votes = (vy_exp / vy_exp.sum()) * self.vy_tuning
            self.vx_non_linear[i] = vx_votes.sum()
            self.vy_non_linear[i] = vy_votes.sum()

        # in the first step the trace can not have a standard deviation --> avoid NANs 
        self.vx_moving_avg[0, 0] = np.sum(self.vx_confidence_binned[self.sorted_indices_vx, 0].mean() * self.vx_tuning)
        self.vy_moving_avg[0, 0] = np.sum(self.vy_confidence_binned[self.sorted_indices_vy, 0].mean() * self.vy_tuning)
        self.vx_moving_avg[0, 1] = 0
        self.vy_moving_avg[0, 1] = 0

        # ---> time INdependent estimates: based on activity of the full run

        # compute the marginalized (over all positions) vx, vy estimates and bin them in a grid
        self.vx_grid = np.linspace(np.min(self.vx_tuning), np.max(self.vx_tuning), self.n_vx_bins, endpoint=True)
        self.vy_grid = np.linspace(np.min(self.vy_tuning), np.max(self.vy_tuning), self.n_vy_bins, endpoint=True)
        self.vx_marginalized_binned = np.zeros(self.n_vx_bins)
        self.vy_marginalized_binned = np.zeros(self.n_vy_bins)
        self.vx_marginalized_binned_nonlinear = np.zeros(self.n_vx_bins)
        self.vy_marginalized_binned_nonlinear = np.zeros(self.n_vy_bins)

        for gid in xrange(self.n_cells):
            vx_cell, vy_cell = self.tuning_prop[gid, 2], self.tuning_prop[gid, 3] # cell properties
            vx_grid_pos, vy_grid_pos = utils.get_grid_pos(vx_cell, vy_cell, self.vx_grid, self.vy_grid)
            self.vx_marginalized_binned[vx_grid_pos] += self.nspikes_normalized[gid]
            self.vy_marginalized_binned[vy_grid_pos] += self.nspikes_normalized[gid]
            self.vx_marginalized_binned_nonlinear[vx_grid_pos] += self.nspikes_normalized_nonlinear[gid]
            self.vy_marginalized_binned_nonlinear[vy_grid_pos] += self.nspikes_normalized_nonlinear[gid]

#        assert (np.sum(self.vx_marginalized_binned) == 1.), "Marginalization incorrect: %.10e" % (np.sum(self.vx_marginalized_binned))
#        assert (np.sum(self.vx_marginalized_binned_nonlinear) == 1.), "Marginalization incorrect: %f" % (np.sum(self.vx_marginalized_binned_nonlinear))
#        assert (np.sum(self.vy_marginalized_binned) == 1.), "Marginalization incorrect: %f" % (np.sum(self.vy_marginalized_binned))
#        assert (np.sum(self.vy_marginalized_binned_nonlinear) == 1.), "Marginalization incorrect: %f" % (np.sum(self.vy_marginalized_binned))

    def compute_theta_estimates(self):

        # time dependent averages
        self.theta_avg = np.arctan2(self.vy_avg, self.vx_avg)
        self.theta_moving_avg = np.zeros((self.n_bins, 2))
        self.theta_moving_avg[:, 0] = np.arctan2(self.vy_moving_avg[:, 0], self.vx_moving_avg[:, 0])
        self.theta_moving_avg[:, 1] = self.theta_uncertainty(self.vx_moving_avg[:, 0], self.vx_moving_avg[:, 1], self.vy_moving_avg[:, 0], self.vy_moving_avg[:, 1])
        self.theta_non_linear = np.arctan2(self.vy_non_linear, self.vx_non_linear)

        # full run estimates
        all_thetas = np.arctan2(self.tuning_prop[:, 3], self.tuning_prop[:, 2])
        self.theta_grid = np.linspace(np.min(all_thetas), np.max(all_thetas), self.n_vx_bins, endpoint=True)
        self.theta_marginalized_binned = np.zeros(self.n_vx_bins)
        self.theta_marginalized_binned_nonlinear = np.zeros(self.n_vx_bins)
        for gid in xrange(self.n_cells):
            theta = np.arctan2(self.tuning_prop[gid, 3], self.tuning_prop[gid, 2])
            grid_pos = utils.get_grid_pos_1d(theta, self.theta_grid)
            self.theta_marginalized_binned[grid_pos] += self.nspikes_normalized[gid]
            self.theta_marginalized_binned_nonlinear[grid_pos] += self.nspikes_normalized_nonlinear[gid]

#        assert (np.sum(self.theta_marginalized_binned) == 1), "Marginalization incorrect: %.1f" % (np.sum(self.theta_marginalized_binned))
#        assert (np.sum(self.theta_marginalized_binned_nonlinear) == 1), "Marginalization incorrect: %.1f" % (np.sum(self.theta_marginalized_binned_nonlinear))


    def plot(self):
        print "plotting ...."
        self.fig1 = pylab.figure()
        pylab.subplots_adjust(hspace=0.95)
        pylab.subplots_adjust(wspace=0.3)

    def plot_nspikes_binned(self):

        self.ax1 = self.fig1.add_subplot(421)
        self.ax1.set_title('Spiking activity over time')
        self.cax1 = self.ax1.pcolor(self.nspikes_binned)
        self.ax1.set_ylim((0, self.nspikes_binned[:, 0].size))
        self.ax1.set_xlim((0, self.nspikes_binned[0, :].size))
        self.ax1.set_xlabel('Time [ms]')
        self.ax1.set_ylabel('GID')
        self.ax1.set_xticks(range(self.n_bins)[::2])
        self.ax1.set_xticklabels(['%d' %i for i in self.time_bins[::2]])
        pylab.colorbar(self.cax1)

    def plot_nspikes_binned_normalized(self):

        self.ax2 = self.fig1.add_subplot(422)
        self.ax2.set_title('Normalized activity over time')
        self.cax2 = self.ax2.pcolor(self.nspikes_binned_normalized)
        self.ax2.set_ylim((0, self.nspikes_binned_normalized[:, 0].size))
        self.ax2.set_xlim((0, self.nspikes_binned_normalized[0, :].size))
        self.ax2.set_xlabel('Time [ms]')
        self.ax2.set_ylabel('GID')
        self.ax2.set_xticks(range(self.n_bins)[::2])
        self.ax2.set_xticklabels(['%d' %i for i in self.time_bins[::2]])
        pylab.colorbar(self.cax2)


    def plot_vx_confidence_binned(self):
        self.ax3 = self.fig1.add_subplot(423)
        self.ax3.set_title('Vx confidence over time')
        self.cax3 = self.ax3.pcolor(self.vx_confidence_binned)
        self.ax3.set_ylim((0, self.vx_confidence_binned[:, 0].size))
        self.ax3.set_xlim((0, self.vx_confidence_binned[0, :].size))
        self.ax3.set_xlabel('Time [ms]')
        self.ax3.set_ylabel('$v_x$')
        self.ax3.set_xticks(range(self.n_bins)[::2])
        self.ax3.set_xticklabels(['%d' %i for i in self.time_bins[::2]])
        ny = self.vx_tuning.size
        n_ticks = 4
        yticks = [self.vx_tuning[int(i * ny/n_ticks)] for i in xrange(n_ticks)]
        ylabels = ['%.1e' % i for i in yticks]
        self.ax3.set_yticks([int(i * ny/n_ticks) for i in xrange(n_ticks)])
        self.ax3.set_yticklabels(ylabels)
        self.ax3.set_xticks(range(self.n_bins)[::2])
        self.ax3.set_xticklabels(['%d' %i for i in self.time_bins[::2]])
        pylab.colorbar(self.cax3)



    def plot_vy_confidence_binned(self):
        self.ax4 = self.fig1.add_subplot(424)
        self.ax4.set_title('vy confidence over time')
        self.cax4 = self.ax4.pcolor(self.vy_confidence_binned)
        self.ax4.set_ylim((0, self.vy_confidence_binned[:, 0].size))
        self.ax4.set_xlim((0, self.vy_confidence_binned[0, :].size))
        self.ax4.set_xlabel('Time [ms]')
        self.ax4.set_ylabel('$v_y$')
        self.ax4.set_xticks(range(self.n_bins)[::2])
        self.ax4.set_xticklabels(['%d' %i for i in self.time_bins[::2]])
        ny = self.vy_tuning.size
        n_ticks = 4
        yticks = [self.vy_tuning[int(i * ny/n_ticks)] for i in xrange(n_ticks)]
        ylabels = ['%.1e' % i for i in yticks]
        self.ax4.set_yticks([int(i * ny/n_ticks) for i in xrange(n_ticks)])
        self.ax4.set_yticklabels(ylabels)
        self.ax4.set_xticks(range(self.n_bins)[::2])
        self.ax4.set_xticklabels(['%d' %i for i in self.time_bins[::2]])
        pylab.colorbar(self.cax4)


    def plot_vx_estimates(self):
        self.ax5 = self.fig1.add_subplot(425)
        self.ax5.set_title('$v_{x}$-predictions: avg, moving_avg, nonlinear')
        self.ax5.plot(self.t_axis, self.vx_avg, ls='-')
        self.ax5.errorbar(self.t_axis, self.vx_moving_avg[:, 0], yerr=self.vx_moving_avg[:, 1], ls='--')
        self.ax5.plot(self.t_axis, self.vx_non_linear, ls=':')
        self.ax5.set_xlabel('Time [ms]')
        self.ax5.set_ylabel('$v_x$')
        ny = self.t_axis.size
        n_ticks = 5
        t_ticks = [self.t_axis[int(i * ny/n_ticks)] for i in xrange(n_ticks)]
        t_labels= ['%d' % i for i in t_ticks]
        self.ax5.set_xticks(t_ticks)
        self.ax5.set_xticklabels(t_labels)

    def plot_vy_estimates(self):
        self.ax6 = self.fig1.add_subplot(426)
        self.ax6.set_title('$v_{y}$-predictions: avg, moving_avg, nonlinear')
        self.ax6.plot(self.t_axis, self.vy_avg, ls='-')
        self.ax6.errorbar(self.t_axis, self.vy_moving_avg[:, 0], yerr=self.vy_moving_avg[:, 1], ls='--')
        self.ax6.plot(self.t_axis, self.vy_non_linear, ls=':')
        self.ax6.set_xlabel('Time [ms]')
        self.ax6.set_ylabel('$v_y$')
        ny = self.t_axis.size
        n_ticks = 5
        t_ticks = [self.t_axis[int(i * ny/n_ticks)] for i in xrange(n_ticks)]
        t_labels= ['%d' % i for i in t_ticks]
        self.ax6.set_xticks(t_ticks)
        self.ax6.set_xticklabels(t_labels)

    def plot_theta_estimates(self):
        self.ax7 = self.fig1.add_subplot(427)
        self.ax7.set_title('$\Theta$-predictions: avg, moving_avg, nonlinear')
        self.ax7.plot(self.t_axis, self.theta_avg, ls='-')
        self.ax7.errorbar(self.t_axis, self.theta_moving_avg[:, 0], yerr=self.theta_moving_avg[:, 1], ls='--')
        self.ax7.plot(self.t_axis, self.theta_non_linear, ls=':')
        self.ax7.set_xlabel('Time [ms]')
        self.ax7.set_ylabel('$\Theta$')
        ny = self.t_axis.size
        n_ticks = 5
        t_ticks = [self.t_axis[int(i * ny/n_ticks)] for i in xrange(n_ticks)]
        t_labels= ['%d' % i for i in t_ticks]
        self.ax7.set_xticks(t_ticks)
        self.ax7.set_xticklabels(t_labels)

    def plot_fullrun_estimates(self):
        self.fig2 = pylab.figure()
        pylab.rcParams['legend.fontsize'] = 10
        pylab.subplots_adjust(hspace=0.5)
        self.plot_fullrun_estimates_vx()
        self.plot_fullrun_estimates_vy()
        self.plot_fullrun_estimates_theta()


    def plot_fullrun_estimates_vx(self):
        self.ax8 = self.fig2.add_subplot(411)
        bin_width = .5 * (self.vx_grid[1] - self.vx_grid[0])
        vx_linear = (np.sum(self.vx_grid * self.vx_marginalized_binned), self.get_uncertainty(self.vx_marginalized_binned, self.vx_grid))
        vx_nonlinear = (np.sum(self.vx_grid * self.vx_marginalized_binned_nonlinear), self.get_uncertainty(self.vx_marginalized_binned_nonlinear, self.vx_grid))
        self.ax8.bar(self.vx_grid, self.vx_marginalized_binned, width=bin_width, label='Linear votes: $v_x=%.2f \pm %.2f$' % (vx_linear[0], vx_linear[1]))
        self.ax8.bar(self.vx_grid+bin_width, self.vx_marginalized_binned_nonlinear, width=bin_width, facecolor='g', label='Non-linear votes: $v_x=%.2f \pm %.2f$' % (vx_nonlinear[0], vx_nonlinear[1]))
        self.ax8.set_title('Estimates based on full run activity with %s connectivity\nblue: linear marginalization over all positions, green: non-linear voting' % self.params['connectivity'])
        self.ax8.set_xlabel('$v_x$')
        self.ax8.set_ylabel('Confidence')
        self.ax8.legend()


    def get_uncertainty(self, p, v):
        """
        p, v are vectors storing the confidence of the voters in p, and the values they vote for in v.
        The uncertainty is estimated as:
        sum_i p_i * (1. - p_i) * v_i
        Idea behind it:
        (1. - p_i) * v_i gives the uncertainty for each vote of v_i
        multiplying it with p_i takes into account how much weight this uncertainty should have in the overall vote
        """
        uncertainties = (np.ones(len(p)) - p) * v
        weighted_uncertainties = p * uncertainties
        return np.sum(weighted_uncertainties)

    def plot_fullrun_estimates_vy(self):
        self.ax9 = self.fig2.add_subplot(412)
        bin_width = .5 * (self.vy_grid[1] - self.vy_grid[0])
        vy_linear = (np.sum(self.vy_grid * self.vy_marginalized_binned), self.get_uncertainty(self.vy_marginalized_binned, self.vy_grid))
        vy_nonlinear = (np.sum(self.vy_grid * self.vy_marginalized_binned_nonlinear), self.get_uncertainty(self.vy_marginalized_binned_nonlinear, self.vy_grid))
        self.ax9.bar(self.vy_grid, self.vy_marginalized_binned, width=bin_width, label='Linear votes: $v_y=%.2f \pm %.2f$' % (vy_linear[0], vy_linear[1]))
        self.ax9.bar(self.vy_grid+bin_width, self.vy_marginalized_binned_nonlinear, width=bin_width, facecolor='g', label='Non-linear votes: $v_y=%.2f \pm %.2f$' % (vy_nonlinear[0], vy_nonlinear[1]))
        self.ax9.set_xlabel('$v_y$')
        self.ax9.set_ylabel('Confidence')
        self.ax9.legend()

    def plot_fullrun_estimates_theta(self):

        self.ax10 = self.fig2.add_subplot(413)
        bin_width = .5 * (self.theta_grid[-1] - self.theta_grid[-2])
        theta_linear = (np.sum(self.theta_grid * self.theta_marginalized_binned), self.get_uncertainty(self.theta_marginalized_binned, self.theta_grid))
        theta_nonlinear = (np.sum(self.theta_grid * self.theta_marginalized_binned_nonlinear), self.get_uncertainty(self.theta_marginalized_binned_nonlinear, self.theta_grid))
        self.ax10.bar(self.theta_grid, self.theta_marginalized_binned, width=bin_width, label='Linear votes: $\Theta=%.2f \pm %.2f$' % (theta_linear[0], theta_linear[1]))
        self.ax10.bar(self.theta_grid+bin_width, self.theta_marginalized_binned_nonlinear, width=bin_width, facecolor='g', label='Non-linear votes: $\Theta=%.2f \pm %.2f$' % (theta_nonlinear[0], theta_nonlinear[1]))
        self.ax10.bar(self.theta_grid, self.theta_marginalized_binned, width=bin_width)
        self.ax10.bar(self.theta_grid+bin_width, self.theta_marginalized_binned_nonlinear, width=bin_width, facecolor='g')
        self.ax10.set_xlim((-np.pi, np.pi))
        self.ax10.legend()


#        n_bins = 50
#        count, theta_bins = np.histogram(self.theta_tuning, n_bins)
#        pred_avg, x = np.histogram(self.theta_avg_fullrun, n_bins)
#        pred_nonlinear, x = np.histogram(self.theta_nonlinear_fullrun, n_bins)
#        bin_width = theta_bins[1]-theta_bins[0]
#        self.ax10.bar(theta_bins[:-1], pred_avg, width=bin_width*.5)
#        self.ax10.bar(theta_bins[:-1]-.5*bin_width, pred_nonlinear, width=bin_width*.5, facecolor='g')
#        self.ax10.set_xlim((self.theta_tuning.min() - bin_width, self.theta_tuning.max()))
        self.ax10.set_xlabel('$\Theta$')
        self.ax10.set_ylabel('Confidence')

    def plot_nspike_histogram(self):
        self.ax10 = self.fig2.add_subplot(414)
        mean_nspikes = self.nspikes.mean()* 1000./self.params['t_sim'] 
        std_nspikes = self.nspikes.std() * 1000./self.params['t_sim']
        self.ax10.bar(range(self.params['n_exc']), self.nspikes* 1000./self.params['t_sim'], label='$f_{mean} = (%.1f \pm %.1f)$ Hz' % (mean_nspikes, std_nspikes))
        self.ax10.set_xlabel('Cell gids')
        self.ax10.set_ylabel('Output rate $f_{out}$')
        self.ax10.legend()

    def theta_uncertainty(self, vx, dvx, vy, dvy):
        """
        theta = arctan(vy / vx)
        Please check with http://en.wikipedia.org/wiki/Propagation_of_uncertainty
        """
        return vx / (vx**2 + vy**2) * dvy - vy / (vx**2 + vx**2) * dvx
