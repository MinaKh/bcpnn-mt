"""
Simple network with a Poisson spike source projecting to populations of of IF_cond_exp neurons
"""
import time
times = {}
t0 = time.time()
import numpy as np
import numpy.random as nprnd
import sys
import NeuroTools.parameters as ntp
import os
import CreateConnections as CC
import utils
import simulation_parameters
ps = simulation_parameters.parameter_storage()
params = ps.params
import pyNN
exec("from pyNN.%s import *" % params['simulator'])
print 'pyNN.version: ', pyNN.__version__
try:
    from mpi4py import MPI
    USE_MPI = True
    comm = MPI.COMM_WORLD
    pc_id, n_proc = comm.rank, comm.size
    print "USE_MPI:", USE_MPI, 'pc_id, n_proc:', pc_id, n_proc
except:
    USE_MPI = False
    pc_id, n_proc, comm = 0, 1, None
    print "MPI not used"
times['time_to_import'] = time.time() - t0
import NetworkSimModuleNoColumns as NSM

def get_local_indices(pop, offset=0):
    """
    Returns the list of indices (not IDs) local to the MPI node 
    of a population
    """
    list_of_locals = []
    for tgt_id in pop.all():
        tgt = int(tgt_id) - offset - 1 # IDs are 1 aligned
        if pop.is_local(tgt_id) and (tgt < pop.size):
            list_of_locals.append(tgt)
    return list_of_locals


class NetworkModel(object):

    def __init__(self, params, comm):

        self.params = params
        self.debug_connectivity = True
        self.comm = comm
        if self.comm != None:
            self.pc_id, self.n_proc = self.comm.rank, self.comm.size
            print "USE_MPI: yes", '\tpc_id, n_proc:', self.pc_id, self.n_proc
        else:
            self.pc_id, self.n_proc = 0, 1
            print "MPI not used"


    def import_pynn(self):
        """
        This function needs only be called when this class is used in another script as imported module
        """
        import pyNN
        exec("from pyNN.%s import *" % self.params['simulator'])
        print 'import pyNN\npyNN.version: ', pyNN.__version__



    def setup(self, load_tuning_prop=False):

        if load_tuning_prop:
            print 'Loading tuning properties from', self.params['tuning_prop_means_fn']
            self.tuning_prop_exc = np.loadtxt(self.params['tuning_prop_means_fn'])
        else:
            print 'Preparing tuning properties with limited range....'
            x_range = (0, 1.)
            y_range = (0.2, .5)
            u_range = (.05, 1.0)
            v_range = (-.2, .2)
            tp_exc_good, tp_exc_out_of_range = utils.set_limited_tuning_properties(params, y_range, x_range, u_range, v_range, cell_type='exc')
            self.tuning_prop_exc = tp_exc_good
            print 'n_exc within range: ', tp_exc_good[:, 0].size
            print "Saving tuning_prop to file:", params['tuning_prop_means_fn']
            np.savetxt(params['tuning_prop_means_fn'], tp_exc_good)

        indices, distances = utils.sort_gids_by_distance_to_stimulus(self.tuning_prop_exc, self.params['motion_params'], self.params) # cells in indices should have the highest response to the stimulus
        if self.pc_id == 0:
            print "Saving tuning_prop to file:", self.params['tuning_prop_means_fn']
            np.savetxt(self.params['tuning_prop_means_fn'], self.tuning_prop_exc)
            print 'Saving gids to record to: ', self.params['gids_to_record_fn']
            np.savetxt(self.params['gids_to_record_fn'], indices[:self.params['n_gids_to_record']], fmt='%d')

#        np.savetxt(params['gids_to_record_fn'], indices[:params['n_gids_to_record']], fmt='%d')

        if self.comm != None:
            self.comm.Barrier()
        from pyNN.utility import Timer
        self.timer = Timer()
        self.timer.start()
        self.times = {}
        # # # # # # # # # # # # 
        #     S E T U P       #
        # # # # # # # # # # # #
        (delay_min, delay_max) = self.params['delay_range']
        setup(timestep=0.1, min_delay=delay_min, max_delay=delay_max, rng_seeds_seed=self.params['seed'])
        rng_v = NumpyRNG(seed = sim_cnt*3147 + self.params['seed'], parallel_safe=True) #if True, slower but does not depend on number of nodes
        self.rng_conn = NumpyRNG(seed = self.params['seed'], parallel_safe=True) #if True, slower but does not depend on number of nodes

        # # # # # # # # # # # # # # # # # # # # # # # # #
        #     R A N D O M    D I S T R I B U T I O N S  #
        # # # # # # # # # # # # # # # # # # # # # # # # #
        self.v_init_dist = RandomDistribution('normal',
                (self.params['v_init'], self.params['v_init_sigma']),
                rng=rng_v,
                constrain='redraw',
                boundaries=(-80, -60))

        self.times['t_setup'] = self.timer.diff()
        self.times['t_calc_conns'] = 0
        if self.comm != None:
            self.comm.Barrier()

    def create_neurons_with_limited_tuning_properties(self, input_created):
        n_exc = self.tuning_prop_exc[:, 0].size
        n_inh = 0
        if self.params['neuron_model'] == 'IF_cond_exp':
            self.exc_pop = Population(n_exc, IF_cond_exp, self.params['cell_params_exc'], label='exc_cells')
        elif self.params['neuron_model'] == 'EIF_cond_exp_isfa_ista':
            self.exc_pop = Population(n_exc, EIF_cond_exp_isfa_ista, self.params['cell_params_exc'], label='exc_cells')
        else:
            print '\n\nUnknown neuron model:\n\t', self.params['neuron_model']


        self.local_idx_exc = get_local_indices(self.exc_pop, offset=0)
        self.exc_pop.initialize('v', self.v_init_dist)
        if not input_created:
            self.spike_times_container = [ [] for i in xrange(len(self.local_idx_exc))]

#        self.local_idx_inh = get_local_indices(self.inh_pop, offset=self.params['n_exc'])
#        print 'Debug, pc_id %d has local %d inh indices:' % (self.pc_id, len(self.local_idx_inh)), self.local_idx_inh
#        self.inh_pop.initialize('v', self.v_init_dist)
        self.times['t_create'] = self.timer.diff()


    def create(self):
        """
            # # # # # # # # # # # # 
            #     C R E A T E     #
            # # # # # # # # # # # #
        """
        if self.params['neuron_model'] == 'IF_cond_exp':
            self.exc_pop = Population(self.params['n_exc'], IF_cond_exp, self.params['cell_params_exc'], label='exc_cells')
            self.inh_pop = Population(self.params['n_inh'], IF_cond_exp, self.params['cell_params_inh'], label="inh_pop")
#        elif self.params['neuron_model'] == 'EIF_cond_exp_isfa_ista':
        elif self.params['neuron_model'] == 'EIF_cond_alpha_isfa_ista':
            self.exc_pop = Population(self.params['n_exc'], EIF_cond_exp_isfa_ista, self.params['cell_params_exc'], label='exc_cells')
            self.inh_pop = Population(self.params['n_inh'], EIF_cond_exp_isfa_ista, self.params['cell_params_inh'], label="inh_pop")
        else:
            print '\n\nUnknown neuron model:\n\t', self.params['neuron_model']
        self.local_idx_exc = get_local_indices(self.exc_pop, offset=0)

        if not input_created:
            self.spike_times_container = [ [] for i in xrange(len(self.local_idx_exc))]

        self.exc_pop.initialize('v', self.v_init_dist)

        self.local_idx_inh = get_local_indices(self.inh_pop, offset=self.params['n_exc'])
        self.inh_pop.initialize('v', self.v_init_dist)

        self.times['t_create'] = self.timer.diff()


    def connect(self):
        self.connect_input_to_exc()
        self.connect_populations('ee')
#        self.connect_populations('ei')
#        self.connect_populations('ie')
#        self.connect_populations('ii')
        self.connect_noise()
        self.times['t_connect'] = self.timer.diff()
        if self.comm != None:
            self.comm.Barrier()

    def create_input(self, load_files=False, save_output=False):


        if load_files:
            if self.pc_id == 0:
                print "Loading input spiketrains..."
            for i_, tgt in enumerate(self.local_idx_exc):
                try:
                    fn = self.params['input_st_fn_base'] + str(tgt) + '.npy'
                    spike_times = np.load(fn)
                except: # this cell does not get any input
                    print "Missing file: ", fn
                    spike_times = []
                self.spike_times_container[i_] = spike_times
        else:
            if self.pc_id == 0:
                print "Computing input spiketrains..."
            nprnd.seed(self.params['input_spikes_seed'])
            dt = self.params['dt_rate'] # [ms] time step for the non-homogenous Poisson process 
            time = np.arange(0, self.params['t_sim'], dt)
            blank_idx = np.arange(1./dt * self.params['t_before_blank'], 1. / dt * (self.params['t_before_blank'] + self.params['t_blank']))

            my_units = self.local_idx_exc
            n_cells = len(my_units)
            L_input = np.zeros((n_cells, time.shape[0]))
            # get the input signal
            for i_time, time_ in enumerate(time):
                if (i_time % 500 == 0):
                    print "t:", time_
                L_input[:, i_time] = utils.get_input(self.tuning_prop_exc[my_units, :], self.params, time_/1000.)
#                L_input[:, i_time] = utils.get_input(self.tuning_prop_exc[my_units, :], self.params, time_/self.params['t_stimulus'])
                L_input[:, i_time] *= self.params['f_max_stim']
            # blanking 
            for i_time in blank_idx:
                L_input[:, i_time] = 0.

            # create the spike trains
            for i_, unit in enumerate(my_units):
                rate_of_t = np.array(L_input[i_, :]) 
                # each cell will get its own spike train stored in the following file + cell gid
                n_steps = rate_of_t.size
                spike_times = []
                for i in xrange(n_steps):
                    r = nprnd.rand()
                    if (r <= ((rate_of_t[i]/1000.) * dt)): # rate is given in Hz -> 1/1000.
                        spike_times.append(i * dt) 
                self.spike_times_container[i_] = spike_times
                if save_output:
                    output_fn = self.params['input_rate_fn_base'] + str(unit) + '.npy'
                    np.save(output_fn, rate_of_t)
                    output_fn = self.params['input_st_fn_base'] + str(unit) + '.npy'
                    np.save(output_fn, np.array(spike_times))
        self.times['create_input'] = self.timer.diff()
        return self.spike_times_container

    def connect_input_to_exc(self):
        """
            # # # # # # # # # # # # # # # # # # # # # # 
            #     C O N N E C T    I N P U T - E X C  #
            # # # # # # # # # # # # # # # # # # # # # # 
        """
        if self.pc_id == 0:
            print "Connecting input spiketrains..."
        for i_, unit in enumerate(self.local_idx_exc):
            spike_times = self.spike_times_container[i_]
            ssa = create(SpikeSourceArray, {'spike_times': spike_times})
            connect(ssa, self.exc_pop[unit], self.params['w_input_exc'], synapse_type='excitatory')
        self.times['connect_input'] = self.timer.diff()


    def connect_anisotropic(self, conn_type):
        """
        """
        if self.pc_id == 0:
            print 'Connect anisotropic %s - %s' % (conn_type[0].capitalize(), conn_type[1].capitalize())

        (n_src, n_tgt, src_pop, tgt_pop, tp_src, tp_tgt, tgt_cells, syn_type) = self.resolve_src_tgt(conn_type)

        if self.debug_connectivity:
            conn_list_fn = self.params['conn_list_%s_fn_base' % conn_type] + '%d.dat' % (self.pc_id)
            conn_file = open(conn_list_fn, 'w')
            output = ''

        n_src_cells_per_neuron = int(round(self.params['p_%s' % conn_type] * n_src))
        (delay_min, delay_max) = self.params['delay_range']
        for tgt in tgt_cells:
            p = np.zeros(n_src)
            latency = np.zeros(n_src)
            for src in xrange(n_src):
                if conn_type[0] == conn_type[1]: # no self-connection
                    if (src != tgt):
                        p[src], latency[src] = CC.get_p_conn(tp_src[src, :], tp_tgt[tgt, :], params['w_sigma_x'], params['w_sigma_v']) #                            print 'debug pc_id src tgt ', self.pc_id, src, tgt#, int(ID) < self.params['n_exc']
                else: # different populations --> same indices mean different cells, no check for src != tgt
                    p[src], latency[src] = CC.get_p_conn(tp_src[src, :], tp_tgt[tgt, :], params['w_sigma_x'], params['w_sigma_v']) #                            print 'debug pc_id src tgt ', self.pc_id, src, tgt#, int(ID) < self.params['n_exc']

            sorted_indices = np.argsort(p)
            if conn_type[0] == 'e':
                sources = sorted_indices[-n_src_cells_per_neuron:] 
            else:
                if conn_type == 'ii':
                    sources = sorted_indices[1:n_src_cells_per_neuron+1]  # shift indices to avoid self-connection, because p_ii = .0
                else:
                    sources = sorted_indices[:n_src_cells_per_neuron] 
            w = (self.params['w_tgt_in_per_cell_%s' % conn_type] / p[sources].sum()) * p[sources]
            for i in xrange(len(sources)):
                if w[i] > self.params['w_thresh_connection']:
#                        w[i] = max(self.params['w_min'], min(w[i], self.params['w_max']))
                    delay = min(max(latency[sources[i]] * self.params['t_stimulus'], delay_min), delay_max)  # map the delay into the valid range
    #                print 'debug ', delay , ' latency', latency[sources[i]]
    #                delay = min(max(latency[sources[i]] * self.params['delay_scale'], delay_min), delay_max)  # map the delay into the valid range
                    connect(src_pop[sources[i]], tgt_pop[tgt], w[i], delay=delay, synapse_type=syn_type)
                    if self.debug_connectivity:
                        output += '%d\t%d\t%.2e\t%.2e\n' % (sources[i], tgt, w[i], delay) #                    output += '%d\t%d\t%.2e\t%.2e\t%.2e\n' % (sources[i], tgt, w[i], latency[sources[i]], p[sources[i]])


        if self.debug_connectivity:
            if self.pc_id == 0:
                print 'DEBUG writing to file:', conn_list_fn
            conn_file.write(output)
            conn_file.close()



    def resolve_src_tgt(self, conn_type):
        """
        Deliver the correct source and target parameters based on conn_type
        """

        if conn_type == 'ee':
            n_src, n_tgt = self.tuning_prop_exc[:, 0].size, self.tuning_prop_exc[:, 0].size
            src_pop, tgt_pop = self.exc_pop, self.exc_pop
            tgt_cells = self.local_idx_exc
            tp_src = self.tuning_prop_exc
            tp_tgt = self.tuning_prop_exc
            syn_type = 'excitatory'

        elif conn_type == 'ei':
            n_src, n_tgt = self.tuning_prop_exc[:, 0].size, self.tuning_prop_inh[:, 0].size
            src_pop, tgt_pop = self.exc_pop, self.inh_pop
            tgt_cells = self.local_idx_inh
            tp_src = self.tuning_prop_exc
            tp_tgt = self.tuning_prop_inh
            syn_type = 'excitatory'

        elif conn_type == 'ie':
            n_src, n_tgt = self.tuning_prop_inh[:, 0].size, self.tuning_prop_exc[:, 0].size
            src_pop, tgt_pop = self.inh_pop, self.exc_pop
            tgt_cells = self.local_idx_exc
            tp_src = self.tuning_prop_inh
            tp_tgt = self.tuning_prop_exc
            syn_type = 'inhibitory'

        elif conn_type == 'ii':
            n_src, n_tgt = self.tuning_prop_inh[:, 0].size, self.tuning_prop_inh[:, 0].size
            src_pop, tgt_pop = self.inh_pop, self.inh_pop
            tgt_cells = self.local_idx_inh
            tp_src = self.tuning_prop_inh
            tp_tgt = self.tuning_prop_inh
            syn_type = 'inhibitory'

        return (n_src, n_tgt, src_pop, tgt_pop, tp_src, tp_tgt, tgt_cells, syn_type)





    def connect_isotropic(self, conn_type='ee'):
        """
        conn_type must be 'ee', 'ei', 'ie' or 'ii'
        Connect cells in a distant dependent manner:
            p_ij = exp(- d_ij / (2 * w_sigma_x**2))

        This will give a 'convergence constrained' connectivity, i.e. each cell will have the same sum of incoming weights 
        ---> could be problematic for outlier cells
        """
        if self.pc_id == 0:
            print 'Connect isotropic %s - %s' % (conn_type[0].capitalize(), conn_type[1].capitalize())

        (n_src, n_tgt, src_pop, tgt_pop, tp_src, tp_tgt, tgt_cells, syn_type) = self.resolve_src_tgt(conn_type)
        if conn_type == 'ee':
            w_= self.params['w_max']
            w_tgt_in = params['w_tgt_in_per_cell_%s' % conn_type]

        elif conn_type == 'ei':
            w_= self.params['w_ie_mean']
            w_tgt_in = params['w_tgt_in_per_cell_%s' % conn_type]

        elif conn_type == 'ie':
            w_= self.params['w_ie_mean']
            w_tgt_in = params['w_tgt_in_per_cell_%s' % conn_type]

        elif conn_type == 'ii':
            w_= self.params['w_ii_mean']
            w_tgt_in = params['w_tgt_in_per_cell_%s' % conn_type]

        if self.debug_connectivity:
            conn_list_fn = self.params['conn_list_%s_fn_base' % conn_type] + '%d.dat' % (self.pc_id)
            conn_file = open(conn_list_fn, 'w')
            output = ''

        p_max = utils.get_pmax(self.params['p_%s' % conn_type])
        for tgt in tgt_cells:
            w = np.zeros(n_src, dtype='float32') 
            delays = np.zeros(n_src, dtype='float32')
            for src in xrange(n_src):
                if (src != tgt):
#                    d_ij = np.sqrt((tp_src[src, 0] - tp_tgt[tgt, 0])**2 + (tp_src[src, 1] - tp_tgt[tgt, 1])**2)
                    d_ij = utils.torus_distance2D(tp_src[src, 0], tp_tgt[tgt, 0], tp_src[src, 1], tp_tgt[tgt, 1])
                    p_ij = p_max * np.exp(-d_ij / (2 * params['w_sigma_x']**2))
                    if np.random.rand() <= p_ij:
                        w[src] = w_
                        delays[src] = d_ij * self.params['delay_scale']
            w *= w_tgt_in / w.sum()
            srcs = w.nonzero()[0]
            for src in srcs:
                if w[src] > self.params['w_thresh_connection']:
                    delay = min(max(delays[src], self.params['delay_range'][0]), self.params['delay_range'][1])  # map the delay into the valid range
                    connect(src_pop[int(src)], tgt_pop[int(tgt)], w[src], delay=delay, synapse_type=syn_type)
                    output += '%d\t%d\t%.2e\t%.2e\n' % (src, tgt, w[src], delay) 
    #                connect(src_pop[int(src)], tgt_pop[int(tgt)], w[src], delay=params['standard_delay'], synapse_type=syn_type)
    #                output += '%d\t%d\t%.2e\t%.2e\n' % (src, tgt, w[src], params['standard_delay']) 
                    
        if self.debug_connectivity:
            if self.pc_id == 0:
                print 'DEBUG writing to file:', conn_list_fn
            conn_file.write(output)
            conn_file.close()

#   isotropic nearest neighbour code:
#        for tgt in tgt_cells:
#            n_src_to_choose = int(round(p_max * n_src)) # guarantee that all cells have same number of connections
#            dist = np.zeros(n_src, dtype='float32')
#            for src in xrange(n_src):
#                if (src != tgt):
#                    dist[src] = np.sqrt((tp_src[src, 0] - tp_tgt[tgt, 0])**2 + (tp_src[src, 1] - tp_tgt[tgt, 1])**2)
#            src_idx = dist.argsort()[:n_src_to_choose] # choose cells closest to the target
#            for src in src_idx:
#                connect(src_pop[int(src)], tgt_pop[int(tgt)], w_, delay=params['standard_delay'], synapse_type='excitatory')
#                output += '%d\t%d\t%.2e\t%.2e\n' % (src, tgt, w_, params['standard_delay']) 



    def connect_random(self, conn_type):
        """
        There exist different possibilities to draw random connections:
        1) Calculate the weights as for the anisotropic case and sample sources randomly
        2) Load a file which stores some random connectivity --> # connector = FromFileConnector(self.params['conn_list_.... ']
        3) Create a random distribution with similar parameters as the non-random connectivition distribution

        connector_ee = FastFixedProbabilityConnector(self.params['p_ee'], weights=w_ee_dist, delays=self.delay_dist)
        prj_ee = Projection(self.exc_pop, self.exc_pop, connector_ee, target='excitatory')

        conn_list_fn = self.params['random_weight_list_fn'] + str(sim_cnt) + '.dat'
        print "Connecting exc - exc from file", conn_list_fn
        connector_ee = FromFileConnector(conn_list_fn)
        prj_ee = Projection(self.exc_pop, self.exc_pop, connector_ee, target='excitatory')
        """
        if self.pc_id == 0:
            print 'Connect random connections %s - %s' % (conn_type[0].capitalize(), conn_type[1].capitalize())
        (n_src, n_tgt, src_pop, tgt_pop, tp_src, tp_tgt, tgt_cells, syn_type) = self.resolve_src_tgt(conn_type)
        w_mean = self.params['w_tgt_in_per_cell_%s' % conn_type] / (n_src * self.params['p_%s' % conn_type])
        w_sigma = w_mean * .5 * (self.params['w_sigma_x'] + self.params['w_sigma_v'])

        weight_distr = RandomDistribution('normal',
                (w_mean, w_sigma),
                rng=self.rng_conn,
                constrain='redraw',
                boundaries=(0, w_mean * 10.))

        delay_dist = RandomDistribution('normal',
                (self.params['standard_delay'], self.params['standard_delay_sigma']),
                rng=self.rng_conn,
                constrain='redraw',
                boundaries=(self.params['delay_range'][0], self.params['delay_range'][1]))

        connector= FastFixedProbabilityConnector(self.params['p_%s' % conn_type], weights=weight_distr, delays=delay_dist)
        prj = Projection(src_pop, tgt_pop, connector, target=syn_type)

        conn_list_fn = self.params['conn_list_%s_fn_base' % conn_type] + '%d.dat' % (self.pc_id)
        print 'Saving random %s connections to %s' % (conn_type, conn_list_fn)
        prj.saveConnections(conn_list_fn, gather=False)



    def connect_populations(self, conn_type):
        """
            # # # # # # # # # # # # 
            #     C O N N E C T   #
            # # # # # # # # # # # # 
            Calls the right according to the flag set in simultation_parameters.py
        """
        if self.params['connectivity_%s' % conn_type] == 'anisotropic':
            self.connect_anisotropic(conn_type)
        elif self.params['connectivity_%s' % conn_type] == 'isotropic':
            self.connect_isotropic(conn_type)
        elif self.params['connectivity_%s' % conn_type] == 'random':
            self.connect_random(conn_type)
        else: # populations do not get connected
            pass
        self.times['t_calc_conns'] += self.timer.diff()


    def connect_noise(self):
        """
            # # # # # # # # # # # # # # # # 
            #     N O I S E   I N P U T   #
            # # # # # # # # # # # # # # # # 
        """
        if self.pc_id == 0:
            print "Connecting noise - exc ... "
        noise_pop_exc = []
        noise_pop_inh = []
        for tgt in self.local_idx_exc:
            #new
            if (self.params['simulator'] == 'nest'): # for nest one can use the optimized Poisson generator
                noise_exc = create(native_cell_type('poisson_generator'), {'rate' : self.params['f_exc_noise']})
                noise_inh = create(native_cell_type('poisson_generator'), {'rate' : self.params['f_inh_noise']})
            else:
                noise_exc = create(SpikeSourcePoisson, {'rate' : self.params['f_exc_noise']})
                noise_inh = create(SpikeSourcePoisson, {'rate' : self.params['f_inh_noise']})
            connect(noise_exc, self.exc_pop[tgt], weight=self.params['w_exc_noise'], synapse_type='excitatory', delay=1.)
            connect(noise_inh, self.exc_pop[tgt], weight=self.params['w_inh_noise'], synapse_type='inhibitory', delay=1.)

#        if self.pc_id == 0:
#            print "Connecting noise - inh ... "
#        for tgt in self.local_idx_inh:
#            if (self.params['simulator'] == 'nest'): # for nest one can use the optimized Poisson generator
#                noise_exc = create(native_cell_type('poisson_generator'), {'rate' : self.params['f_exc_noise']})
#                noise_inh = create(native_cell_type('poisson_generator'), {'rate' : self.params['f_inh_noise']})
#            else:
#                noise_exc = create(SpikeSourcePoisson, {'rate' : self.params['f_exc_noise']})
#                noise_inh = create(SpikeSourcePoisson, {'rate' : self.params['f_inh_noise']})
#            connect(noise_exc, self.inh_pop[tgt], weight=self.params['w_exc_noise'], synapse_type='excitatory', delay=1.)
#            connect(noise_inh, self.inh_pop[tgt], weight=self.params['w_inh_noise'], synapse_type='inhibitory', delay=1.)





    def run_sim(self, sim_cnt, record_v=True):
        # # # # # # # # # # # # # # # # # # # #
        #     P R I N T    W E I G H T S      # 
        # # # # # # # # # # # # # # # # # # # #
        record_exc = True
        if os.path.exists(self.params['gids_to_record_fn']):
            gids_to_record = np.loadtxt(self.params['gids_to_record_fn'], dtype='int')[:self.params['n_gids_to_record']]
            record_exc = True
            n_rnd_cells_to_record = 2
        else:
            n_cells_to_record = 5# self.params['n_exc'] * 0.02
            gids_to_record = np.random.randint(0, self.params['n_exc'], n_cells_to_record)


        if record_v:
            self.exc_pop_view = PopulationView(self.exc_pop, gids_to_record, label='good_exc_neurons')
            self.exc_pop_view.record_v()

        self.exc_pop.record()
        self.times['t_record'] = self.timer.diff()

        if self.pc_id == 0:
            print "Running simulation ... "
        run(self.params['t_sim'])
        self.times['t_sim'] = self.timer.diff()


    def print_results(self, print_v=True):
        """
            # # # # # # # # # # # # # # # # #
            #     P R I N T    R E S U L T S 
            # # # # # # # # # # # # # # # # #
        """
        if print_v:
            if self.pc_id == 0:
                print 'print_v to file: %s.v' % (self.params['exc_volt_fn_base'])
            self.exc_pop_view.print_v("%s.v" % (self.params['exc_volt_fn_base']), compatible_output=False)

        if self.pc_id == 0:
            print "Printing excitatory spikes"
        self.exc_pop.printSpikes(self.params['exc_spiketimes_fn_merged'] + '.ras')
        # print a dummy file for inhibitory
        np.savetxt(self.params['inh_spiketimes_fn_merged'] + '.ras', np.array([]))

        self.times['t_print'] = self.timer.diff()
        if self.pc_id == 0:
            print "calling pyNN.end() ...."
        end()
        self.times['t_end'] = self.timer.diff()

        if self.pc_id == 0:
            self.times['t_all'] = 0.
            for k in self.times.keys():
                self.times['t_all'] += self.times[k]

            self.n_cells = {}
            self.n_cells['n_exc'] = self.params['n_exc']
            self.n_cells['n_inh'] = self.params['n_inh']
            self.n_cells['n_cells'] = self.params['n_cells']
            self.n_cells['n_proc'] = self.n_proc
            output = {'times' : self.times, 'n_cells_proc' : self.n_cells}
            print "Proc %d Simulation time: %d sec or %.1f min for %d cells (%d exc %d inh)" % (self.pc_id, self.times['t_sim'], (self.times['t_sim'])/60., self.params['n_cells'], self.params['n_exc'], self.params['n_inh'])
            print "Proc %d Full pyNN run time: %d sec or %.1f min for %d cells (%d exc %d inh)" % (self.pc_id, self.times['t_all'], (self.times['t_all'])/60., self.params['n_cells'], self.params['n_exc'], self.params['n_inh'])
            fn = utils.convert_to_url(params['folder_name'] + 'times_dict_np%d.py' % self.n_proc)
            output = ntp.ParameterSet(output)
            output.save(fn)


if __name__ == '__main__':

    import simulation_parameters
    ps = simulation_parameters.parameter_storage()
    params = ps.params
    import pyNN
    exec("from pyNN.%s import *" % params['simulator'])
    print 'pyNN.version: ', pyNN.__version__

    try:
        from mpi4py import MPI
        USE_MPI = True
        comm = MPI.COMM_WORLD
        pc_id, n_proc = comm.rank, comm.size
        print "USE_MPI:", USE_MPI, 'pc_id, n_proc:', pc_id, n_proc
    except:
        USE_MPI = False
        pc_id, n_proc, comm = 0, 1, None
        print "MPI not used"


    try:
    # optional, to run parameter sweeps by batch scripts
        p1, p2, p3, p4, p5, p6, p7, p8 = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6]), float(sys.argv[7]), float(sys.argv[8])
        ps.params['w_tgt_in_per_cell_ee'] = p1
        ps.params['w_tgt_in_per_cell_ei'] = p2
        ps.params['w_tgt_in_per_cell_ie'] = p3
        ps.params['w_tgt_in_per_cell_ii'] = p4
        ps.params['w_sigma_x'] = p5
        ps.params['w_sigma_v'] = p6
        ps.params['connectivity_radius'] = p7
        ps.params['delay_scale'] = p8

    except:
        pass


    ps.set_filenames()
    if pc_id == 0:
        ps.create_folders()
        ps.write_parameters_to_file()
    if comm != None:
        comm.Barrier()
    sim_cnt = 0
    record = True
    NM = NetworkModel(ps.params, comm)
    NM.setup()
    input_created = False
    NM.create_neurons_with_limited_tuning_properties(input_created)
    if not input_created:
        spike_times_container = NM.create_input(load_files=False, save_output=True)
        input_created = True # this can be set True ONLY if the parameter does not affect the input
        # i.e. set this to false when sweeping f_max_stim, or blur_X/V!
    else:
        NM.spike_times_container = spike_times_container
    NM.connect()
    NM.run_sim(sim_cnt, record_v=record)
    NM.print_results(print_v=record)

