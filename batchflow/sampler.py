# pylint: disable=too-few-public-methods, method-hidden
""" Contains Sampler-classes. """

from copy import copy
import numpy as np
import scipy.stats as ss

# if empirical probability of truncation region is less than
# this number, truncation throws a ValueError
SMALL_SHARE = 1e-2

# aliases for Numpy, Scipy-Stats, TensorFlow-samplers
ALIASES = {
    'n': {'np': 'normal', 'ss': 'norm', 'tf': 'Normal'},
    'u': {'np': 'uniform', 'ss': 'uniform', 'tf': 'Uniform'},
    'mvn': {'np': 'multivariate_normal', 'ss': 'multivariate_normal'},
    'e': {'np': 'exponential', 'ss': 'expon', 'tf': 'Exponential'},
    'g': {'np': 'gamma', 'ss': 'gamma', 'tf': 'Gamma'},
    'be' : {'np': 'beta', 'ss': 'beta', 'tf': 'Beta'},
    'mnm': {'np': 'multinomial', 'ss': 'multinomial', 'tf': 'Multinomial'},
    'f': {'np': 'f', 'ss': 'f'},
    'p': {'np': 'poisson', 'ss': 'poisson'},
    'w': {'np': 'weibull', 'ss': 'dweibull'},
    'ln': {'np': 'lognormal', 'ss': 'lognorm'},
    'b' : {'np': 'binomial', 'ss': 'binom'},
    'chi2': {'np': 'chisquare', 'ss': 'chi2'},
    'c': {'np': 'choice'}
}

def _get_method_by_alias(alias, module, tf_distributions=None):
    """ Fetch fullname of a randomizer from ``scipy.stats``, ``tensorflow`` or
    ``numpy`` by its alias or fullname.
    """
    rnd_submodules = {'np': np.random,
                      'tf': tf_distributions,
                      'ss': ss}
    # fetch fullname
    fullname = ALIASES.get(alias, {module: alias for module in ['np', 'tf', 'ss']}).get(module, None)
    if fullname is None:
        raise ValueError("Distribution %s has no implementaion in module %s" % (alias, module))

    # check that the randomizer is implemented in corresponding module
    if not hasattr(rnd_submodules[module], fullname):
        raise ValueError("Distribution %s has no implementaion in module %s" % (fullname, module))

    return fullname


def arithmetize(cls):
    """ Add arithmetic operations to Sampler-class.
    """
    for oper in ['__add__', '__mul__', '__truediv__', '__sub__', '__pow__', '__floordiv__', '__mod__']:
        def transform(self, other, fake=oper):
            """ Arithmetic operation on couple of Samplers.

            Implemented via corresponding operation in ndarrays.

            Parameters
            ----------
            other : Sampler
                second Sampler, the operation is applied to.

            Returns
            -------
            Sampler
                resulting sampler.
            """
            _class = classes[fake]
            return _class(self, other)
        setattr(cls, oper, transform)

    return cls

@arithmetize
class Sampler():
    """ Base class Sampler that implements algebra of Samplers.

    Attributes
    ----------
    weight : float
        weight of Sampler self in mixtures.
    """
    def __init__(self, *args, **kwargs):
        self.__array_priority__ = 100
        self.weight = 1.0

        # if dim is supplied, redefine sampling method
        if 'dim' in kwargs:
            # assemble stacked sampler
            dim = kwargs.pop('dim')
            stacked = type(self)(*args, **kwargs)
            for _ in range(dim - 1):
                stacked = type(self)(*args, **kwargs) & stacked

            # redefine sample of self
            self.sample = stacked.sample

    def sample(self, size):
        """ Sampling method of a sampler.

        Parameters
        ----------
        size : int
            lentgh of sample to be generated.

        Returns
        -------
        np.ndarray
            Array of size (len, Sampler's dimension).
        """
        raise NotImplementedError('The method should be implemented in child-classes!')

    def __or__(self, other):
        """ Implementation of '|' operation for two instances of Sampler-class.

        The result is the mixture of two samplers. Weights are taken from
        samplers' weight-attributes.

        Parameters
        ----------
        other : Sampler
            the sampler to be added to self.

        Returns
        -------
        Sampler
            resulting mixture of two samplers.
        """
        return OrSampler(self, other)

    def __and__(self, other):
        """ Implementation of '&' operation for instance of Sampler-class.

        Two cases are possible: if ``other`` is numeric, then "&"-operation changes
        the weight of a sampler. Otherwise, if ``other`` is also a Sampler, the resulting
        Sampler is a multidimensional sampler, with starting coordinates being sampled from
        ``self``, and trailing - from ``other``.

        Parameters
        ----------
        other : int or float or Sampler
            the sampler/weight for multiplication.

        Returns
        -------
        Sampler
            result of the multiplication.
        """
        return AndSampler(self, other)

class OrSampler(Sampler):
    def __init__(self, left, right, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.left = left
        self.right = right

        # calculate probs of samplers in mixture
        _ws = np.array([self.left.weight, self.right.weight])
        self.weight = np.sum(_ws)
        self._normed = _ws / np.sum(_ws)

    def sample(self, size):
        _up_size = np.random.binomial(size, self._normed[0])
        _low_size = size - _up_size

        _up = self.left.sample(size=_up_size)
        _low = self.right.sample(size=_low_size)
        _sample = np.concatenate([_up, _low])
        sample = _sample[np.random.permutation(size)]

        return sample

class AndSampler(Sampler):
    def __init__(self, left, right, *args, **kwargs):
        super.__init__(*args, **kwargs)
        self.left = left
        self.right = right

    def sample(self, size):
        pass

class BaseOperationSampler(Sampler):
    def __init__(self, left, right, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.left = left
        self.right = right

def make_classname(operation='__add__'):
    name = operation.split('__')[1]
    return name.capitalize() + 'Sampler'

def ArithmeticSamplersFactory():
    classes = dict()
    ops = ['__add__', '__mul__', '__truediv__', '__sub__', '__pow__', '__floordiv__', '__mod__']
    for oper in ops:
        name = make_classname(oper)
        def sample(self, size, fake=oper):
            return getattr(self.left.sample(size), fake)(self.right.sample(size))
        classes[oper] = type(name, (BaseOperationSampler, ), {'sample': sample})
    return classes

classes = ArithmeticSamplersFactory()

class NumpySampler(Sampler):
    """ Sampler based on a distribution from np.random.

    Parameters
    ----------
    name : str
        name of a distribution (method from np.random) or its alias.
    seed : int
        random seed for setting up sampler's state.
    **kwargs
        additional keyword-arguments defining properties of specific
        distribution. E.g., ``loc`` for name='normal'.

    Attributes
    ----------
    name : str
        name of a distribution (method from np.random).
    _params : dict
        dict of args for Sampler's distribution.
    """
    def __init__(self, name, seed=None, **kwargs):
        super().__init__(name, seed, **kwargs)
        name = _get_method_by_alias(name, 'np')
        self.name = name
        self._params = copy(kwargs)
        self.state = np.random.RandomState(seed=seed)


    def sample(self, size):
        """ Sampling method of ``NumpySampler``.

        Generates random samples from distribution ``self.name``.

        Parameters
        ----------
        size : int
            the size of sample to be generated.

        Returns
        -------
        np.ndarray
            array of shape (size, Sampler's dimension).
        """
        sampler = getattr(self.state, self.name)
        sample = sampler(size=size, **self._params)
        if len(sample.shape) == 1:
            sample = sample.reshape(-1, 1)
        return sample
