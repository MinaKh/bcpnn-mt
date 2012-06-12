import pylab
import numpy as np
import sys
# --------------------------------------------------------------------------
#def get_figsize(fig_width_pt):
#    inches_per_pt = 1.0/72.0                # Convert pt to inch
#    golden_mean = (np.sqrt(5)-1.0)/2.0    # Aesthetic ratio
#    fig_width = fig_width_pt*inches_per_pt  # width in inches
#    fig_height = fig_width*golden_mean      # height in inches
#    fig_size =  [fig_width,fig_height]      # exact figsize
#    return fig_size

#params2 = {'backend': 'png',
#          'axes.labelsize': 12,
#          'text.fontsize': 12,
#          'xtick.labelsize': 12,
#          'ytick.labelsize': 12,
#          'legend.pad': 0.2,     # empty space around the legend box
#          'legend.fontsize': 12,
#          'lines.markersize' : 0.1,
#          'font.size': 12,
#          'path.simplify': False,
#          'figure.figsize': get_figsize(800)}

#def set_figsize(fig_width_pt):
#    pylab.rcParams['figure.figsize'] = get_figsize(fig_width_pt)

#pylab.rcParams.update(params2)

# --------------------------------------------------------------------------


fn = sys.argv[1]

rate = np.load(fn)
#data = pylab.loadtxt(fn)
fn = sys.argv[2]
spikes = np.load(fn) # spikedata

#spikes *= 10. # because rate(t) = L(t) was created with a stepsize of .1 ms

n, bins = np.histogram(spikes, bins=20)
print 'n, bins', n, 'total', np.sum(n), bins

fig = pylab.figure()
ax = fig.add_subplot(211)

rate_half = .5 * (np.max(rate) - np.min(rate))
print 'spikes', spikes.size
ax.plot(spikes, rate_half * np.ones(spikes.size), '|', markersize=1)
print 'rate', rate
rate = rate[::10]
ax.plot(np.arange(rate.size), rate)
ax = fig.add_subplot(212)
ax.bar(bins[:-1], n)

#output_fn = 'delme.dat'
#np.savetxt(output_fn, data)
output_fn = 'delme.png'
print output_fn
pylab.savefig(output_fn)
pylab.show()