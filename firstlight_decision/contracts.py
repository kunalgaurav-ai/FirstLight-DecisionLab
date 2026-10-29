"""Spec-authored, frozen precommit checks. NOT extracted from published JSON gold.

The first six tasks are DEV (their previous failures have been inspected).
Eight disjoint tasks are prospective HOLDOUT. Tests are committed in the source ZIP
before running any holdout model calls and controller cannot read gold tests.
"""
from firstlight_v55.sandbox import PROBES as DEV_PROBES
DEV = tuple(DEV_PROBES)
HOLDOUT = ('bitcount','get_factors','pascal','sieve','max_sublist_sum','mergesort','quicksort','find_first_in_sorted')
HOLDOUT_PROBES = {
 'bitcount': [ [[0],0], [[7],3], [[1048577],2] ],
 'get_factors': [ [[8],[2,2,2]], [[12],[2,2,3]], [[49],[7,7]] ],
 'pascal': [ [[6],[[1],[1,1],[1,2,1],[1,3,3,1],[1,4,6,4,1],[1,5,10,10,5,1]]], [[7],[[1],[1,1],[1,2,1],[1,3,3,1],[1,4,6,4,1],[1,5,10,10,5,1],[1,6,15,20,15,6,1]]] ],
 'sieve': [ [[3],[2,3]], [[10],[2,3,5,7]], [[30],[2,3,5,7,11,13,17,19,23,29]] ],
 'max_sublist_sum': [ [[[-1,-2]],0], [[[2,-5,5,1,-1,3]],8], [[[1,-2,3,4,-1]],7] ],
 'mergesort': [ [[[3,1,2]],[1,2,3]], [[[9]], [9]], [[[2,2,1]],[1,2,2]] ],
 'quicksort': [ [[[2,1,2]],[1,2,2]], [[[]],[]], [[[-1,3,0,-1]],[-1,-1,0,3]] ],
 'find_first_in_sorted': [ [[[1,2,2,2,3],2],1], [[[],3],-1], [[[1,2,2,3],4],-1] ],
}
# Explicit dev-only non-gold performance/invariant checks; compare to regular probes
# and report timing/quality separately. Frozen before holdout.
DEV_STRESS = {
 'levenshtein': [[['kitten','sitting'],3], [['abcdabcd','abdcabdc'],2]],
 'find_in_sorted': [[[[2,4,6,8],1],-1], [[[1,3,5,7],8],-1]],
 'rpn_eval': [[[[5.0,2.0,'-']],3.0], [[[2.0,3.0,'+']],5.0]],
}
ALL = DEV + HOLDOUT

def probes(name):
 if name in HOLDOUT_PROBES:return HOLDOUT_PROBES[name]
 if name in DEV_PROBES:return DEV_PROBES[name]+DEV_STRESS.get(name,[])
 raise KeyError('NO_AUTHORED_PRECOMMIT_CONTRACT:'+name)
