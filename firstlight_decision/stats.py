"""Finite-sample paired descriptive statistics; no automatic commercial claims."""
from math import comb
from random import Random

def exact_discordance_p(wins,losses):
    """Two-sided exact paired sign/McNemar p for binary task outcomes."""
    if wins<0 or losses<0:raise ValueError('NEGATIVE_COUNT')
    n=wins+losses
    if not n:return 1.0
    k=min(wins,losses)
    return min(1.0,2*sum(comb(n,i) for i in range(k+1))/(2**n))

def paired_bootstrap(values,seed=1517,draws=2500):
    """Within-task paired mean bootstrap CI. Unreliable for small or dependent tasks."""
    if not values:return None
    rng=Random(seed);n=len(values)
    means=[]
    for _ in range(draws):means.append(sum(values[rng.randrange(n)] for j in range(n))/n)
    means.sort()
    return {'mean':sum(values)/n,'low_95':means[int(.025*(draws-1))],
            'high_95':means[int(.975*(draws-1))],
            'unit':'PER_TASK','status':'EXPLORATORY_TASK_BOOTSTRAP_NOT_GENERALIZATION_GUARANTEE'}
