import scipy.sparse
import scipy.sparse.linalg
import numpy as np
import pickle
from sklearn.preprocessing import normalize

from scipy.sparse.sputils import matrix


class Tester:
    def __init__(self) -> None:
        print('inited')


A = np.array([
    [0, 1, 0],
    [1, 0, 0],
    [0, 3, 0]
])

B = scipy.sparse.csc_matrix(A)

C = np.array([
    [1],
    [2],
    [3]
])

D = scipy.sparse.csc_matrix(C)

sp = scipy.sparse.lil_matrix((4, 6))

sp[1, 2] = 5
sp[1, 0] = 3
sp[0, 1] = 2
sp[0, 2] = 7

X = sp.tocsc()

U, S, VT = scipy.sparse.linalg.svds(X, k=2)
D = np.diag(S)
print(VT)
print()
S = D @ VT
print(S)
query = np.array([1, 0, 0, 1]).reshape((-1, 1))

print(query.T @ U @ S)
