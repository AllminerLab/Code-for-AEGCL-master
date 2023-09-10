import numpy as np
import os.path as osp
from pGRACE.dataset import get_dataset
from sklearn.neighbors import NearestNeighbors
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--datasetname', type=str, default='Amazon-Photo')
parser.add_argument('--k', type=int, default=5)
args = parser.parse_args()

datasetname = args.datasetname
k = args.k
path = osp.expanduser('datasets')
path = osp.join(path, datasetname)
dataset = get_dataset(path, datasetname)
data = dataset[0]

neigh = NearestNeighbors(n_neighbors=k)
X = data.x.numpy().tolist()
neigh.fit(X)
A = neigh.kneighbors_graph(X)
A = A.toarray()
np.save('temp/' + datasetname + '/adj_knn_' + str(k) + '.npy', A)