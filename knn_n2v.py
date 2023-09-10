import numpy as np
from sklearn.neighbors import NearestNeighbors

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--datasetname', type=str, default='Amazon-Photo')
parser.add_argument('--k', type=int, default=5)
args = parser.parse_args()

datasetname = args.datasetname
k = args.k

n2v_emb = np.load('temp/' + datasetname + '/n2vemb.npy')

neigh = NearestNeighbors(n_neighbors=k)
X = n2v_emb.tolist()
neigh.fit(X)
A = neigh.kneighbors_graph(X)
A = A.toarray()
np.save('temp/' + datasetname + '/adj_knn_n2v_' + str(k) + '.npy', A)