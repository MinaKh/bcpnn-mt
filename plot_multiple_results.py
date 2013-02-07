import pylab
import numpy as np
import sys

#pylab.rcParams.update({'path.simplify' : False})
pylab.figure()

for fn in sys.argv[1:]:
    try:
        data = np.loadtxt(fn)# , skiprows=1)
    except:
        data = np.load(fn)# , skiprows=1)
    if (data.ndim == 1):
        print 'ndim = 1'
        x_axis = np.arange(data.size)
        pylab.plot(x_axis, data, lw=1, label=fn)
#        pylab.scatter(x_axis, data)
    else:
#        x_axis = np.arange(data[:, 0].size)
#        pylab.plot(x_axis, data[:,0], lw=1, label=fn)
        x_axis = data[:, 0]
        pylab.plot(x_axis, data[:,1], lw=1, label=fn)
#        pylab.errorbar(x_axis, data[:,1], yerr=data[:, 2], lw=1, label=fn)

#        pylab.plot(data[:,0], data[:,1], lw=2, label=fn)
#        pylab.scatter(np.arange(0, data[:, 0].size), data[:, 0], label=fn)

#output_fn = 'delme_out.png'
#print 'output_fn:', output_fn 
#pylab.savefig(output_fn)

pylab.legend()#]fontsize='small')
pylab.show()
