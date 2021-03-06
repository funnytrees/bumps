from __future__ import division
__all__ = ['plot_all', 'plot_corr', 'plot_corrmatrix',
           'plot_trace', 'plot_vars', 'plot_var',
           'plot_R','plot_logp', 'format_vars']

import math
import re

import numpy
from numpy import arange, squeeze, linspace, meshgrid, vstack, inf
from . import corrplot
from .stats import credible_interval, stats
from .formatnum import format_uncertainty, format_value

def plot_all(state, portion=1.0, figfile=None):
    from pylab import figure, savefig, suptitle

    figure(); vstats = plot_vars(state, portion=portion)
    if state.title: suptitle(state.title)
    print format_vars(vstats)
    if figfile != None: savefig(figfile+"-vars")
    figure(); plot_trace(state, portion=portion)
    if state.title: suptitle(state.title)
    if figfile != None: savefig(figfile+"-trace")
    figure(); plot_R(state, portion=portion)
    if state.title: suptitle(state.title)
    if figfile != None: savefig(figfile+"-R")
    figure(); plot_logp(state, portion=portion)
    if state.title: suptitle(state.title)
    if figfile != None: savefig(figfile+"-logp")
    if state.Nvar <= 25:
        figure(); plot_corrmatrix(state, portion=portion)
        if state.title: suptitle(state.title)
        if figfile != None: savefig(figfile+"-corr")

def plot_var(state, var=0, portion=None, selection=None, **kw):
    points, logp = state.sample(portion=portion, vars=[var],
                                selection=selection)
    _plot_var(points.flatten(), logp, label=state.labels[var], **kw)

# TODO: separate var stats calculation from plotting and printing
def plot_vars(state, vars=None, portion=1.0, selection=None, **kw):
    from pylab import subplot,cm,clf

    clf()
    points, logp = state.sample(portion=portion, vars=vars,
                                selection=selection)
    if vars==None:
        vars = range(points.shape[1])
    nw,nh = tile_axes(len(vars))
    vstats = []
    cbar = _make_fig_colorbar(logp)
    for k,v in enumerate(vars):
        subplot(nw,nh,k+1)
        vstats.append(_plot_var(points[:,k].flatten(), logp, cbar,
                                  label=state.labels[v], index=k, **kw))
    return vstats

def tile_axes(n, size=None):
    """
    Creates a tile for the axes which covers as much area of the graph as
    possible while keeping the plot shape near the golden ratio.
    """
    from pylab import gcf
    if size == None:
        size = gcf().get_size_inches()
    figwidth, figheight = size
    # Golden ratio phi is the preferred dimension
    #    phi = sqrt(5)/2
    #
    # nw, nh is the number of tiles across and down respectively
    # w, h are the sizes of the tiles
    #
    # w,h = figwidth/nw, figheight/nh
    #
    # To achieve the golden ratio, set w/h to phi:
    #     w/h = phi  => figwidth/figheight*nh/nw = phi
    #                => nh/nw = phi * figheight/figwidth
    # Must have enough tiles:
    #     nh*nw > n  => nw > n/nh
    #                => nh**2 > n * phi * figheight/figwidth
    #                => nh = floor(sqrt(n*phi*figheight/figwidth))
    #                => nw = ceil(n/nh)
    phi = math.sqrt(5)/2
    nh = int(math.floor(math.sqrt(n*phi*figheight/figwidth)))
    if nh<1: nh = 1
    nw = int(math.ceil(n/nh))
    return nw,nh


def _plot_var(points, logp, cbar, index=None, label="P", nbins=30, ci=0.95):
    # Sort the data
    idx = numpy.argsort(points)
    points = points[idx]
    logp=logp[idx]
    idx = numpy.argmax(logp)
    maxlogp = logp[idx]
    best = points[idx]

    # If weighted, use the relative probability from the marginal distribution
    # as the weight
    #weights = numpy.exp(logp-maxlogp) if weighted else None
    weights = None

    # Choose the interval for the histogram
    ONE_SIGMA = 0.15865525393145705
    rangeci,range68 = credible_interval(x=points, weights=weights,
                                        ci=[ci,1-2*ONE_SIGMA])

    mean, std, median = stats(x=points, weights=weights)

    vstats = dict(label=label, index=index, rangeci=rangeci, range68=range68,
                  median=median, mean=mean, std=std, best=best)


    #_make_var_histogram(points, logp, nbins, rangeci, weights)
    _make_logp_histogram(points, logp, nbins, rangeci, weights, cbar)
    _decorate_histogram(vstats)
    return vstats

def _decorate_histogram(vstats):
    import pylab
    from matplotlib.transforms import blended_transform_factory as blend
    # Shade things inside 1-sigma
    pylab.axvspan(vstats['range68'][0],vstats['range68'][1],
                  color='gold',alpha=0.5,zorder=-1)
    # build transform with x=data, y=axes(0,1)
    ax = pylab.gca()
    transform = blend(ax.transData, ax.transAxes)

    lci,hci = vstats['rangeci']
    l68,h68 = vstats['range68']
    mean,median,best = vstats['mean'],vstats['median'],vstats['best']
    def marker(s,v):
        if v < lci: s,v,ha = '<'+s,lci,'left'
        elif v > hci: s,v,ha = '>'+s,hci,'right'
        else: ha='center'
        pylab.text(v, 0.95, s, va='top', ha=ha,
                   transform=transform, zorder=3, color='g')
        #pylab.axvline(v)
    marker('|',median)
    marker('E',mean)
    marker('*',best)

    pylab.text(0.01, 0.95, vstats['label'], zorder=2,
        backgroundcolor=(1,1,0,0.2),
        verticalalignment='top',
        horizontalalignment='left',
        transform=pylab.gca().transAxes)
    pylab.setp([pylab.gca().get_yticklabels()],visible=False)
    ticks = (lci, l68, median, h68, hci)
    labels = [format_value(v,hci-lci) for v in ticks]
    if len(labels[2]) > 5:
        # Drop 68% values if too many digits
        ticks,labels= ticks[0::2],labels[0::2]
    pylab.xticks(ticks, labels)

def _make_fig_colorbar(logp):
    import matplotlib as mpl
    import pylab

    # Option 1: min to min + 4
    #vmin=-max(logp); vmax=vmin+4
    # Option 1b: min to min log10(num samples)
    #vmin=-max(logp); vmax=vmin+log10(len(logp))
    # Option 2: full range of best 98%
    snllf = pylab.sort(-logp)
    vmin,vmax = snllf[0],snllf[int(0.98*(len(snllf)-1))] # robust range
    # Option 3: full range
    #vmin,vmax = -max(logp),-min(logp)

    fig = pylab.gcf()
    ax = fig.add_axes([0.60, 0.95, 0.35, 0.05])
    cmap = pylab.cm.copper

    # Set the colormap and norm to correspond to the data for which
    # the colorbar will be used.
    norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

    # ColorbarBase derives from ScalarMappable and puts a colorbar
    # in a specified axes, so it has everything needed for a
    # standalone colorbar.  There are many more kwargs, but the
    # following gives a basic continuous colorbar with ticks
    # and labels.
    class MinDigitsFormatter(mpl.ticker.Formatter):
        def __init__(self, vmin, vmax):
            self.delta = vmax-vmin
        def __call__(self, x, pos=None):
            return format_value(x, self.delta)
    ticks = (vmin,vmax)
    formatter = MinDigitsFormatter(vmin,vmax)
    cb = mpl.colorbar.ColorbarBase(ax, cmap=cmap, norm=norm, 
                                   ticks=ticks, format=formatter,
                                   orientation='horizontal')
    #cb.set_ticks(ticks)
    #cb.set_ticklabels(labels)
    #cb.set_label('negative log likelihood')

    return vmin,vmax,cmap



def _make_logp_histogram(points, logp, nbins, rangeci, weights, cbar):
    from numpy import (ones_like, searchsorted, linspace, cumsum, diff, 
        sort, argsort, array, hstack, log10, exp)
    if weights == None: weights = ones_like(logp)
    edges = linspace(rangeci[0],rangeci[1],nbins+1)
    idx = searchsorted(points, edges)
    weightsum = cumsum(weights)
    heights = diff(weightsum[idx])/weightsum[-1]  # normalized weights

    import pylab
    vmin,vmax,cmap = cbar
    cmap_steps = linspace(vmin,vmax,cmap.N+1)
    bins = [] # marginalized maximum likelihood
    for h,s,e,xlo,xhi in zip(heights,idx[:-1],idx[1:],edges[:-1],edges[1:]):
        if s == e: continue
        pv = -logp[s:e]
        pidx = argsort(pv)
        pw = weights[s:e][pidx]
        x = array([xlo,xhi],'d')
        y = hstack((0,cumsum(pw)))  
        z = pv[pidx][:,None]
        # centerpoint, histogram height, maximum likelihood for each bin
        bins.append(((xlo+xhi)/2,y[-1],exp(vmin-z[0])))
        if len(z) > cmap.N:
           # downsample histogram bar according to number of colors
           pidx = searchsorted(z[1:-1].flatten(), cmap_steps)
           if pidx[-1] < len(z)-1: pidx = hstack((pidx,-1))
           y,z = y[pidx],z[pidx]
        pylab.pcolormesh(x,y,z,vmin=vmin,vmax=vmax,hold=True,cmap=cmap)
        # Draw bars around each histogram bin
        #pylab.plot([xlo,xlo,xhi,xhi],[y[0],y[-1],y[-1],y[0]],'-k',linewidth=0.1,hold=True)
    centers,height,maxlikelihood = array(bins).T
    pylab.plot(centers, maxlikelihood*max(height), '-g', hold=True)

def _make_var_histogram(points, logp, nbins, rangeci, weights):
    # Produce a histogram
    hist, bins = numpy.histogram(points, bins=nbins, range=rangeci,
                                 #new=True,
                                 normed=True, weights=weights)

    # Find the max likelihood for values in each bin
    edge = numpy.searchsorted(points,bins)
    histbest = [numpy.max(logp[edge[i]:edge[i+1]])
                if edge[i]<edge[i+1] else -inf
                for i in range(nbins)]

    # scale to marginalized probability with peak the same height as hist
    histbest = numpy.exp(histbest-maxlogp)
    histbest *= numpy.max(hist)


    import pylab
    # Plot the histogram
    pylab.bar(bins[:-1], hist, width=bins[1]-bins[0])

    # Plot the kernel density estimate
    #density = kde_1d(points)
    #x = linspace(bins[0],bins[-1],100)
    #pylab.plot(x, density(x), '-k', hold=True)

    # Plot the marginal maximum likelihood
    centers = (bins[:-1]+bins[1:])/2
    pylab.plot(centers, histbest, '-g', hold=True)

def format_num(x, place):
    precision = 10**place
    digits_after_decimal = abs(place) if place < 0 else 0
    return "%.*f"%(digits_after_decimal,
                   numpy.round(x/precision)*precision)

def format_vars(varstats, ci=0.95):
    v = dict(parameter="Parameter",
             mean="mean", median="median", best="best",
             interval68="68% interval",
             intervalci="%g%% interval"%(100*ci))
    s = ["   %(parameter)20s %(mean)10s %(median)7s %(best)7s [%(interval68)15s] [%(intervalci)15s]"%v]
    for v in varstats:
        label,index = v['label'],v['index']
        rangeci,range68 = v['rangeci'],v['range68']
        median, mean, std, best = v['median'],v['mean'],v['std'],v['best']
        # Make sure numbers are formatted with the appropriate precision
        place = int(numpy.log10(rangeci[1]-rangeci[0]))-2
        summary = dict(mean=format_uncertainty(mean,std),
                       median=format_num(median,place-1),
                       best=format_num(best,place-1),
                       lo68=format_num(range68[0],place),
                       hi68=format_num(range68[1],place),
                       ci="%g%%"%(100*ci),
                       loci=format_num(rangeci[0],place),
                       hici=format_num(rangeci[1],place),
                       parameter=label,
                       index=index+1)
        s.append("%(index)2d %(parameter)20s %(mean)10s %(median)7s %(best)7s [%(lo68)7s %(hi68)7s] [%(loci)7s %(hici)7s]"%summary)

    return "\n".join(s)

VAR_PATTERN = re.compile(r"""
   ^\ *
   (?P<parnum>[0-9]+)\ +
   (?P<parname>.+?)\ +
   (?P<mean>[0-9.-]+?)
   \((?P<err>[0-9]+)\)
   (e(?P<exp>[+-]?[0-9]+))?\ +
   (?P<median>[0-9.eE+-]+?)\ +
   (?P<best>[0-9.eE+-]+?)\ +
   \[\ *(?P<lo68>[0-9.eE+-]+?)\ +
   (?P<hi68>[0-9.eE+-]+?)\]\ +
   \[\ *(?P<lo95>[0-9.eE+-]+?)\ +
   (?P<hi95>[0-9.eE+-]+?)\]
   \ *$
   """, re.VERBOSE)

class VarStats(object):
    def __init__(self, **kw):
        self.__dict__ = kw

def parse_var(line):
    """
    Parse a line returned by format_vars back into the statistics for the
    variable on that line.
    """
    m = VAR_PATTERN.match(line)
    if m:
        exp = int(m.group('exp')) if m.group('exp') else 0
        return VarStats(number = int(m.group('parnum')),
                        name = m.group('parname'),
                        mean = float(m.group('mean')) * 10**exp,
                        median = float(m.group('median')),
                        best = float(m.group('best')),
                        p68 = (float(m.group('lo68')), float(m.group('hi68'))),
                        p95 = (float(m.group('lo95')), float(m.group('hi95'))),
                        )
    else:
        return None


def plot_corrmatrix(state, vars=None, portion=None, selection=None):
    points, _ = state.sample(portion=portion, vars=vars, selection=selection)
    labels = state.labels if vars==None else [state.labels[v] for v in vars]
    c = corrplot.Corr2d(points.T, bins=50, labels=labels)
    c.plot()
    #print "Correlation matrix\n",c.R()


from scipy.stats import kde
class kde_1d(kde.gaussian_kde):
    covariance_factor = lambda self: 2*self.silverman_factor()

class kde_2d(kde.gaussian_kde):
    covariance_factor = kde.gaussian_kde.silverman_factor
    def __init__(self, dataset):
        kde.gaussian_kde.__init__(self, dataset.T)
    def evalxy(self, x, y):
        X,Y = meshgrid(x,y)
        dxy = self.evaluate(vstack([X.flatten(),Y.flatten()]))
        return dxy.reshape(X.shape)
    __call__ = evalxy

def plot_corr(state, vars=(0,1), portion=None, selection=None):
    from pylab import axes, setp, MaxNLocator

    p1,p2 = vars
    labels = [state.labels[v] for v in vars]
    points, _ = state.sample(portion=portion, vars=vars, selection=selection)

    # Form kernel density estimates of the parameters
    xmin,xmax = min(points[:,0]),max(points[:,0])
    density_x = kde_1d(points[:,0])
    x = linspace(xmin, xmax, 100)
    px = density_x(x)

    density_y = kde_1d(points[:,1])
    ymin,ymax = min(points[:,1]),max(points[:,1])
    y = linspace(ymin, ymax, 100)
    py = density_y(y)

    nbins = 50
    axData = axes([0.1,0.1,0.63,0.63]) # x,y,w,h

    #density_xy = kde_2d(points[:,vars])
    #dxy = density_xy(x,y)*points.shape[0]
    #axData.pcolorfast(x,y,dxy,cmap=cm.gist_earth_r) #@UndefinedVariable

    axData.plot(points[:,0], points[:,1], 'k.', markersize=1)
    axData.set_xlabel(labels[0])
    axData.set_ylabel(labels[1])
    axHistX = axes([0.1,0.75,0.63,0.2],sharex=axData)
    axHistX.hist(points[:,0],nbins,orientation='vertical',normed=1)
    axHistX.plot(x,px,'k-')
    axHistX.yaxis.set_major_locator(MaxNLocator(4,prune="both"))
    setp(axHistX.get_xticklabels(), visible=False,)
    axHistY = axes([0.75,0.1,0.2,0.63],sharey=axData)
    axHistY.hist(points[:,1],nbins,orientation='horizontal',normed=1)
    axHistY.plot(py,y,'k-')
    axHistY.xaxis.set_major_locator(MaxNLocator(4,prune="both"))
    setp(axHistY.get_yticklabels(), visible=False)

def plot_trace(state, var=0, portion=None):
    from pylab import plot, title, xlabel, ylabel

    draw, points, _ = state.chains()
    start = int((1-portion)*len(draw)) if portion else 0
    plot(arange(start,len(points))*state.thinning,
         squeeze(points[start:,state._good_chains,var]))
    title('Parameter history for variable %d'%(var+1))
    xlabel('Generation number')
    ylabel('Parameter value')

def plot_R(state, portion=None):
    from pylab import plot, title, legend, xlabel, ylabel

    draw, R = state.R_stat()
    start = int((1-portion)*len(draw)) if portion else 0
    plot(arange(start,len(R)), R[start:])
    title('Convergence history')
    legend(['P%d'%i for i in range(1,R.shape[1]+1)])
    xlabel('Generation number')
    ylabel('R')

def plot_logp(state, portion=None):
    from pylab import plot, title, xlabel, ylabel

    draw, logp = state.logp()
    start = int((1-portion)*len(draw)) if portion else 0
    plot(arange(start,len(logp)), logp[start:], '.', markersize=1)
    title(r'Log Likelihood History')
    xlabel('Generation number')
    ylabel('Log likelihood at x[k]')
