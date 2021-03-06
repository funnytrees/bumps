"""
Bounds handling.

Use bounds(low, high, style) to create a bounds handling object.  This
function operates on a point x, transforming it so that all dimensions
are within the bounds.  Options are available, including reflecting,
wrapping, clipping or randomizing the point, or ignoring the bounds.

The returned bounds object should have an apply(x) method which
transforms the point *x*.
"""
__all__ = ['set_bounds']
from numpy import inf, isinf, asarray
from . import util

def make_bounds_handler(bounds, style='reflect'):
    """
    Return a bounds object which can update the bounds.

    Bounds handling *style* name is one of::

        reflect:   reflect off the boundary
        clip:      stop at the boundary
        fold:      wrap values to the other side of the boundary
        randomize: move to a random point in the bounds
        none:      ignore the bounds

    With semi-infinite intervals folding and randomizing aren't well
    defined, and reflection is used instead.

    With finite intervals the the reflected or folded point may still be
    outside the bounds (which can happen if the step size is too large),
    and a random uniform value is used instead.
    """
    if bounds == None:
        return IgnoreBounds()

    low,high = bounds

    # Do boundary handling -- what to do when points fall outside bound
    style = style.lower()
    if style == 'reflect':
        f = ReflectBounds(low, high)
    elif style == 'clip':
        f = ClipBounds(low, high)
    elif style == 'fold':
        f = FoldBounds(low, high)
    elif style == 'randomize':
        f = RandomBounds(low, high)
    elif style == 'none' or style == None:
        f = IgnoreBounds()
    else:
        raise ValueError("bounds style %s is not valid"%style)
    return f

class Bounds(object):
    def apply(self, x):
        raise NotImplementedError
    def __call__(self, pop):
        for x in pop: self.apply(x)
        return pop

class ReflectBounds(Bounds):
    """
    Reflect parameter values into bounded region
    """
    def __init__(self, low, high):
        self.low, self.high = [asarray(v,'d') for v in low, high]

    def apply(self, y):
        """
        Update x so all values lie within bounds

        Returns x for convenience.  E.g., y = bounds.apply(x+0)
        """
        minn, maxn = self.low, self.high

        # Reflect points which are out of bounds
        idx = y < minn; y[idx] = 2*minn[idx] - y[idx]
        idx = y > maxn; y[idx] = 2*maxn[idx] - y[idx]

        # Randomize points which are still out of bounds
        idx = (y < minn) | (y > maxn)
        y[idx] = minn[idx] + util.RNG.rand(sum(idx))*(maxn[idx]-minn[idx])
        return y

class ClipBounds(Bounds):
    """
    Clip values to bounded region
    """
    def __init__(self, low, high):
        self.low, self.high = [asarray(v,'d') for v in low, high]

    def apply(self, y):
        minn, maxn = self.low, self.high
        idx = y < minn; y[idx] = minn[idx]
        idx = y > maxn; y[idx] = maxn[idx]

        return y

class FoldBounds(Bounds):
    """
    Wrap values into the bounded region
    """
    def __init__(self, low, high):
        self.low, self.high = [asarray(v,'d') for v in low, high]

    def apply(self, y):
        minn, maxn = self.low, self.high

        # Deal with semi-infinite cases using reflection
        idx = (y < minn) & isinf(maxn); y[idx] = 2*minn[idx] - y[idx]
        idx = (y > maxn) & isinf(minn); y[idx] = 2*maxn[idx] - y[idx]

        # Wrap points which are out of bounds
        idx = y < minn; y[idx] = maxn[idx] - (minn[idx] - y[idx])
        idx = y > maxn; y[idx] = minn[idx] + (y[idx] - maxn[idx])

        # Randomize points which are still out of bounds
        idx = (y < minn) | (y > maxn)
        y[idx] = minn[idx] + util.RNG.rand(sum(idx))*(maxn[idx]-minn[idx])

        return y

class RandomBounds(Bounds):
    """
    Randomize values into the bounded region
    """
    def __init__(self, low, high):
        self.low, self.high = [asarray(v,'d') for v in low, high]

    def apply(self, y):
        minn, maxn = self.low, self.high

        # Deal with semi-infinite cases using reflection
        idx = (y < minn) & isinf(maxn); y[idx] = 2*minn[idx] - y[idx]
        idx = (y > maxn) & isinf(minn); y[idx] = 2*maxn[idx] - y[idx]

        # The remainder are selected uniformly from the bounded region
        idx = (y < minn) | (y > maxn)
        y[idx] = minn[idx] + util.RNG.rand(sum(idx))*(maxn[idx]-minn[idx])

        return y

class IgnoreBounds(Bounds):
    """
    Leave values outside the bounded region
    """
    def __init__(self, low=None, high=None):
        self.low, self.high = [asarray(v,'d') for v in low, high]

    def apply(self, y):
        return y

def test():
    from numpy.linalg import norm
    from numpy import array
    bounds = zip( [5,10], [-inf,-10], [-5,inf], [-inf,inf] )
    v = asarray([6,-12, 6,-12],'d')
    for t in 'none', 'reflect', 'clip', 'fold', 'randomize':
        assert norm(make_bounds_handler(bounds, t).apply(v+0) - v) == 0
    v = asarray([12,12,-12,-12],'d')
    for t in 'none', 'reflect', 'clip', 'fold':
        w = make_bounds_handler(bounds, t)
        assert norm(w(array([v,v,v])) - w.apply(v+0)) == 0
    assert norm(make_bounds_handler(bounds, 'none').apply(v+0) - v) == 0
    assert norm(make_bounds_handler(bounds, 'reflect').apply(v+0) - [8, -32, 2, -12]) == 0
    assert norm(make_bounds_handler(bounds, 'clip').apply(v+0) - [10, -10, -5, -12]) == 0
    assert norm(make_bounds_handler(bounds, 'fold').apply(v+0) - [7, -32, 2, -12]) == 0
    w = make_bounds_handler(bounds, 'randomize').apply(v+0)
    assert 5<=w[0]<=10 and w[1]==-32 and w[2]==2 and w[3]==-12
    v = asarray([20, 1, 1, 1],'d')
    w = make_bounds_handler(bounds, 'reflect').apply(v+0)
    assert 5<=w[0]<=10
    v = asarray([20, 1, 1, 1],'d')
    w = make_bounds_handler(bounds, 'fold').apply(v+0)
    assert 5<=w[0]<=10

if __name__ == "__main__":
    test()
