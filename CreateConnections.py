import numpy as np
import numpy.random as rnd
import utils
from scipy.spatial import distance
import os
import time

def get_p_conn(tp_src, tp_tgt, w_sigma_x, w_sigma_v):
    """
    tp_src is a list/array with the 4 tuning property values of the source cell: x, y, u, v
        
    Latex code for formulas:
    \delta_{latency} = \frac{\sqrt{d_{torus}(x_0, x_1)^2 + d_{torus}(y_0, y_1)^2}}{\sqrt{u_0^2 + v_0^2}}
    x_{predicted} = x_0 + u_0 \cdot \delta_{latency}
    y_{predicted} = y_0 + v_0 \cdot \delta_{latency}
    p = exp(-\frac{(d_{torus}(x_{predicted}, x_1))^2 + (d_{torus}(y_{predicted}, y_1))^2}{2 \cdot \sigma_{space}^2})
        \cdot exp(-\frac{(u_0-u_1)^2 + (v_0 - v_1)^2}{2 \cdot \sigma_V^2})
 
    """

    x0 = tp_src[0]
    y0 = tp_src[1]
    u0 = tp_src[2]
    v0 = tp_src[3]
    x1 = tp_tgt[0]
    y1 = tp_tgt[1]
    u1 = tp_tgt[2]
    v1 = tp_tgt[3]
    dx = utils.torus_distance(x0, x1)
    dy = utils.torus_distance(y0, y1)
    latency = np.sqrt(dx**2 + dy**2) / np.sqrt(u0**2 + v0**2)
    x_predicted = x0 + u0 * latency  
    y_predicted = y0 + v0 * latency  
    p = np.exp(-.5 * (utils.torus_distance(x_predicted, x1))**2 / w_sigma_x**2 \
               -.5 * (utils.torus_distance(y_predicted, y1))**2 / w_sigma_x**2) \
      * np.exp(-.5 * (u0 - u1)**2 / w_sigma_v ** 2 \
               -.5 * (v0 - v1)**2 / w_sigma_v ** 2)
    return p, latency

def get_tp_distance(tp_src, tp_tgt, w_sigma_x, w_sigma_v):
    """
    tp_src is a list/array with the 4 tuning property values of the source cell: x, y, u, v
        
    Latex code for formulas:
    \delta_{latency} = \frac{\sqrt{d_{torus}(x_0, x_1)^2 + d_{torus}(y_0, y_1)^2}}{\sqrt{u_0^2 + v_0^2}}
    x_{predicted} = x_0 + u_0 \cdot \delta_{latency}
    y_{predicted} = y_0 + v_0 \cdot \delta_{latency}
    p = exp(-\frac{(d_{torus}(x_{predicted}, x_1))^2 + (d_{torus}(y_{predicted}, y_1))^2}{2 \cdot \sigma_{space}^2})
        \cdot exp(-\frac{(u_0-u_1)^2 + (v_0 - v_1)^2}{2 \cdot \sigma_V^2})
 
    """

    x0 = tp_src[0]
    y0 = tp_src[1]
    u0 = tp_src[2]
    v0 = tp_src[3]
    x1 = tp_tgt[0]
    y1 = tp_tgt[1]
    u1 = tp_tgt[2]
    v1 = tp_tgt[3]
    dx = utils.torus_distance(x0, x1)
    dy = utils.torus_distance(y0, y1)
    latency = np.sqrt(dx**2 + dy**2) / np.sqrt(u0**2 + v0**2)
    x_predicted = x0 + u0 * latency  
    y_predicted = y0 + v0 * latency  
    p = np.exp(-((utils.torus_distance(x_predicted, x1))**2 + (utils.torus_distance(y_predicted, y1))**2 / (2 * w_sigma_x**2))) \
            * np.exp(-((u0-u1)**2 + (v0 - v1)**2) / (2 * w_sigma_v**2))
    return p, latency


def compute_weights_convergence_constrained(tuning_prop, params, comm=None):
    """
    This function computes for each target the X % of source cells which have the highest
    connection probability to the target cell.

    Arguments:
        tuning_prop: 2 dimensional array with shape (n_cells, 4)
            tp[:, 0] : x-position
            tp[:, 1] : y-position
            tp[:, 2] : u-position (speed in x-direction)
            tp[:, 3] : v-position (speed in y-direction)
    """
    if comm != None:
        pc_id, n_proc = comm.rank, comm.size
        comm.barrier()
    else:
        pc_id, n_proc = 0, 1
    gid_min, gid_max = utils.distribute_n(params['n_exc'], n_proc, pc_id)
    sigma_x, sigma_v = params['w_sigma_x'], params['w_sigma_v'] # small sigma values let p and w shrink
    (delay_min, delay_max) = params['delay_range']
    output_fn = params['conn_list_ee_conv_constr_fn_base'] + 'pid%d.dat' % (pc_id)
    print "Proc %d computes initial weights for gids (%d, %d) to file %s" % (pc_id, gid_min, gid_max, output_fn)
    conn_file = open(output_fn, 'w')
    my_cells = range(gid_min, gid_max)
    n_src_cells = round(params['p_ee'] * params['n_exc']) # number of sources per target neuron
    output = np.zeros((len(my_cells), n_src_cells+1), dtype='int')
    weights = np.zeros((len(my_cells), n_src_cells+1), dtype='int')

    output = ''
    cnt = 0
    for tgt in my_cells:
        p = np.zeros(params['n_exc'])
        latency = np.zeros(params['n_exc'])
        for src in xrange(params['n_exc']):
            if (src != tgt):
                p[src], latency[src] = get_p_conn(tuning_prop[src, :], tuning_prop[tgt, :], sigma_x, sigma_v)
        sorted_indices = np.argsort(p)
        sources = sorted_indices[-params['n_src_cells_per_neuron']:] 
        w = params['w_tgt_in'] / p[sources].sum() * p[sources]
#        w = utils.linear_transformation(w, params['w_min'], params['w_max'])
        for i in xrange(len(sources)):
#            w[i] = max(params['w_min'], min(w[i], params['w_max']))
            src = sources[i]
            delay = min(max(latency[src] * params['delay_scale'], delay_min), delay_max)  # map the delay into the valid range
            d_ij = utils.euclidean(tuning_prop[src, :], tuning_prop[tgt, :])
            output += '%d\t%d\t%.2e\t%.2e\t%.2e\n' % (src, tgt, w[i], delay, d_ij)
            cnt += 1

    print 'PID %d Writing %d connections to file: %s' % (pc_id, cnt, output_fn)
    conn_file.write(output)
    conn_file.close()

    if (comm != None):
        comm.barrier()




def compute_weights_from_tuning_prop(tuning_prop, params, comm=None):
    """
    Arguments:
        tuning_prop: 2 dimensional array with shape (n_cells, 4)
            tp[:, 0] : x-position
            tp[:, 1] : y-position
            tp[:, 2] : u-position (speed in x-direction)
            tp[:, 3] : v-position (speed in y-direction)
    """

    n_cells = tuning_prop[:, 0].size
    sigma_x, sigma_v = params['w_sigma_x'], params['w_sigma_v'] # small sigma values let p and w shrink
    (delay_min, delay_max) = params['delay_range']
    if comm != None:
        pc_id, n_proc = comm.rank, comm.size
        comm.barrier()
    else:
        pc_id, n_proc = 0, 1
    output_fn = params['conn_list_ee_fn_base'] + 'pid%d.dat' % (pc_id)
    print "Proc %d computes initial weights to file %s" % (pc_id, output_fn)
    gid_min, gid_max = utils.distribute_n(params['n_exc'], n_proc, pc_id)
    n_cells = gid_max - gid_min
    my_cells = range(gid_min, gid_max)
    output = ""

    i = 0
    for src in my_cells:
        for tgt in xrange(params['n_exc']):
            if (src != tgt):
                p, latency = get_p_conn(tuning_prop[src, :], tuning_prop[tgt, :], sigma_x, sigma_v)
                delay = min(max(latency * params['delay_scale'], delay_min), delay_max)  # map the delay into the valid range
                output += '%d\t%d\t%.4e\t%.2e\n' % (src, tgt, p, delay)
                i += 1

    print 'Process %d writes connections to: %s' % (pc_id, output_fn)
    f = file(output_fn, 'w')
    f.write(output)
    f.flush()
    f.close()
    normalize_probabilities(params, comm, params['w_thresh_connection'])
    if (comm != None):
        comm.barrier()


def normalize_probabilities(params, comm, w_thresh=None):
    """
    Open all files named with params['conn_list_ee_fn_base'], sum the last 3rd column storing the probabilities,
    reopen all the files, divide by the sum, and save all the files again.
    
    """
    if comm != None:
        pc_id, n_proc = comm.rank, comm.size
    else:
        pc_id, n_proc = 0, 1

    fn = params['conn_list_ee_fn_base'] + 'pid%d.dat' % (pc_id)
    print 'Reading', fn
    d = np.loadtxt(fn)


    p_sum = d[:, 2].sum()
    if comm != None:
        p_sum_global = comm.allreduce(p_sum, None)
    else:
        p_sum_global = p_sum

    d[:, 2] /= p_sum_global
    d[:, 2] *= params['p_to_w_scaling']

    if w_thresh != None:
        indices = np.nonzero(d[:, 2] > w_thresh)[0]
        d = d[indices, :] # resize the output array

    fn = params['conn_list_ee_fn_base'] + 'pid%d_normalized.dat' % (pc_id)
    print 'Writing to ', fn
    np.savetxt(fn, d, fmt='%d\t%d\t%.4e\t%.2e')

    # make one file out of many
#    if pc_id == 0:
#        data = ''
#        for pid in xrange(n_proc):
#            fn = params['conn_list_ee_fn_base'] + 'pid%d_normalized.dat ' % (pid)
#            f = file(fn, 'r')
#            data += f.readlines()
#        output_fn = params['conn_list_ee_fn_base'] + '0.dat'
#        f = file(output_fn, 'w')
#        f.write(data)
#        f.flush()
#        f.close()

    if pc_id == 0:
        cat_command = 'cat '
        for pid in xrange(n_proc):
            fn = params['conn_list_ee_fn_base'] + 'pid%d_normalized.dat ' % (pid)
            cat_command += fn
        output_fn = params['conn_list_ee_fn_base'] + '0.dat'
        cat_command += ' > %s' % output_fn
        print 'Merging to:', output_fn
        os.system(cat_command)

def get_exc_inh_connections(pred_pos, inh_pos, tp_exc, n=10):
    """
    This function calculates the adjacency matrix for the exc to inh connections.
    Input:
     pred_pos : array of x, y values storing the positions approximately predicted by exc cells (pred_pos = (x, y) + (u, v))
     pred_pos[i, 0] : x-pos of exc cell i
     pred_pos[i, 1] : y-pos of exc cell i
    
     inh_pos : same format as pred_pos, positions of inhibitory cells
     n : number of incoming connections per target cell

    Returns :
     one adjacency list with n_inh lines containing the exc cell indices connecting to the inh cell in the given line
     - one list of same size with the distances 
    """

    n_tgt = inh_pos[:, 0].size
    n_src = pred_pos[:, 0].size
    output_indices, output_distances = np.zeros((n_tgt, n)), np.zeros((n_tgt, n))
    for tgt in xrange(n_tgt):
        # calculate the distance between the target and all sources
        dist = np.zeros(n_src)
        x0, y0 = inh_pos[tgt, 0], inh_pos[tgt, 1]
#        for src in xrange(n_src):
#            x1, y1 = pred_pos[src, 0], pred_pos[src, 1]
#            dx = utils.torus_distance(x0, x1)
#            dy = utils.torus_distance(y0, y1)
#            dist[src] = np.sqrt(dx**2 + dy**2)
        # choose n most distance indices
#        idx = dist.argsort()[-n:]

        # calculate the scalar product between the vector exc-inh and the predicted vector
        abs_scalar_products = np.zeros(n_src)
        for src in xrange(n_src):
            x_e, y_e = tp_exc[src, 0], tp_exc[src, 1]
            x_pred, y_pred = pred_pos[src, 0], pred_pos[src, 1]
            v_exc_inh = (x0 - x_e, y0 - y_e)
            v_exc_pred = (tp_exc[src, 2], tp_exc[src, 3])
#            v_exc_pred= (x_pred - x_e, y_pred - y_e)
            abs_scalar_products[src] = abs(sum(v_exc_inh[i] * v_exc_pred[i] for i in xrange(len(v_exc_inh))))

        # choose those indices with smallest scalar product (smallest projection of v_exc_pred onto v_exc_inh)
        idx = abs_scalar_products.argsort()[:n]
        output_indices[tgt, :] = idx
        for i in xrange(n):
            src = idx[i]
            dx = utils.torus_distance(pred_pos[src, 0], inh_pos[tgt, 0])
            dy = utils.torus_distance(pred_pos[src, 1], inh_pos[tgt, 1])
            output_distances[tgt, i] = np.sqrt(dx**2 + dy**2)

    return output_indices, output_distances




def compute_random_weight_list(input_fn, output_fn, params, seed=98765):
    """
    Open the existing pre-computed (non-random) conn_list and shuffle sources and targets
    """
    rnd.seed(seed)
    d = np.loadtxt(input_fn)
#    d[:, 0] = rnd.randint(0, params['n_exc'], d[:, 0].size)
#    d[:, 1] = rnd.randint(0, params['n_exc'], d[:, 0].size)
    rnd.shuffle(d[:, 0])    # shuffle source ids
#    rnd.shuffle(d[:, 1])    # shuffle target ids
#    rnd.shuffle(d[:, 3])    # shuffle delays ids

    np.savetxt(output_fn, d)


def create_initial_connection_matrix(n, output_fn, w_max=1.0, sparseness=0.0, seed=1234):
    """
    Returns an initial connection n x n matrix with a sparseness parameter.
    Sparseness is betwee 0 and 1.
    if sparseness == 0: return full matrix
    if sparseness != 0: set sparseness * n * m elements to 0
    if sparseness == 1: return empty matrix
    """
    rnd.seed(seed)
    d = rnd.rand(n, n) * w_max
    print "debug", d[0, 1], d[0, 3]
    # set the diagonal elements to zero
    for i in xrange(n):
        d[i, i] = 0

    if (sparseness != 0.0):
        z = (sparseness * n**2 - n) # ignore the diagonal
        cnt = 0
        while cnt <= z:
            d[rnd.randint(0, n), rnd.randint(0, n)] = 0.
            cnt += 1
    np.savetxt(output_fn, d)
    return d



def create_conn_list_by_random_normal(output_fn, sources, targets, p, w_mean, w_sigma, d_mean=0., d_sigma=0., d_min=1):
    """
    This function writes a conn list with normal distributed weights (and delays) to output_fn.
    Arguments:
        output_fn: string
        sources: tuple with min_gid and max_gid
    """
    conns = []
    for src in xrange(sources[0], sources[1]):
        for tgt in xrange(targets[0], targets[1]):
            if rnd.rand() <= p:
                w = -1
                while (w < 0):
                    w = rnd.normal(w_mean, w_sigma)
                if d_sigma != 0.:
                    d = -1
                    while (d <= 0):
                        d = rnd.normal(d_mean, d_sigma)
                else:
                    d = d_min
                conns.append([src, tgt, w, d])
    output_array = np.array(conns)
    np.savetxt(output_fn, output_array)


            

