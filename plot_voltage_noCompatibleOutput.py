import random
import numpy as np
import sys
import pylab
import utils



def plot_volt(fn, gid=None, n=1):
    print 'loading', fn
    d = np.loadtxt(fn)

    if gid == None:
        recorded_gids = np.unique(d[:, 0])
        gids = random.sample(recorded_gids, n)
        print 'plotting random gids:', gids
    elif gid == 'all':
        gids = np.unique(d[:, 0])
    elif type(gid) == type([]):
        gids = gid
    else:
        gids = [gid]
    
    for gid in gids:
        time_axis, volt = utils.extract_trace(d, gid)
        pylab.plot(time_axis, volt, label='%d' % gid, lw=2)

    parts = fn.rsplit('.')
    output_fn = "" 
    for i in xrange(len(parts)-1):
        output_fn += "%s" % parts[i] + '.'
    output_fn += 'png'
    pylab.legend()
    pylab.title(fn)
#    print 'Saving to', output_fn
#    pylab.savefig(output_fn)


def plot_average_volt(fn, gid=None, n=1):
    print 'Plotting average voltage; loading', fn
    d = np.loadtxt(fn)
    if gid == None:
        gid_range = np.unique(d[:, 0])
        gids = np.random.randint(np.min(gid_range), np.max(gid_range) + 1, n)
        print 'plotting random gids:', gids
    elif gid == 'all':
        gids = np.unique(d[:, 0])
    elif type(gid) == type([]):
        gids = gid
    else:
        gids = [gid]
    
    time_axis, volt = utils.extract_trace(d, gids[0])
    all_volt = np.zeros((time_axis.size, len(gids)))

    for i_, gid in enumerate(gids):
        time_axis, volt = utils.extract_trace(d, gid)
        print 'gid %d v_mean, std = %.2f +- %.2f; min %.2f max %.2f, diff %.2f ' % (gid, volt.mean(), volt.std(), volt.min(), volt.max(), volt.max() - volt.min())
        all_volt[:, i_] = volt

    avg_volt = np.zeros((time_axis.size, 2))
    for t in xrange(time_axis.size):
        avg_volt[t, 0] = all_volt[t, :].mean()
        avg_volt[t, 1] = all_volt[t, :].std()

    print 'Average voltage and std: %.2e +- %.2e (%.2e)' % (avg_volt[:, 0].mean(), avg_volt[:, 0].std(), avg_volt[:, 1].mean())
    pylab.errorbar(time_axis, avg_volt[:, 0], yerr=avg_volt[:, 1], lw=3, c='k') 


if __name__ == '__main__':
    if len(sys.argv) == 1:
        import simulation_parameters
        ps = simulation_parameters.parameter_storage()
        params = ps.params
        fns = [params['exc_volt_fn_base'] + '.v']
    else:
        fns = sys.argv[1:]
    for fn in fns:
        pylab.figure()

#    fn = sys.argv[1]
#    gids = np.loadtxt('Testing/Parameters/gids_to_record.dat')

#    gids = gids[:5].tolist()
#        gids = [205, 378]
#        gids = [177, 130]
#        plot_volt(fn, gids)

#        n = 5
#        plot_volt(fn, gid=None, n=n)

#        plot_volt(fn, gid=[207])
        plot_volt(fn, gid='all')
#    plot_average_volt(fn, gids)

#    plot_average_volt(fn, gid='all')

    pylab.xlabel('Time [ms]')
    pylab.ylabel('Voltage [mV]')

#    output_fn = fn.rsplit('.')[0] + '.png'
#    print 'Saving to', output_fn
#    pylab.savefig(output_fn)
    pylab.show()

#    plot_volt(fn, n=5)
#    plot_volt(fn, 'all')
