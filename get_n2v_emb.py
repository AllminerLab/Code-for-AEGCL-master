import numpy as np
from subprocess import call
import os.path as osp
from pGRACE.dataset import get_dataset
import argparse

def str_list_to_float(str_list):
    return [float(item) for item in str_list]

def read_embeddings(filename, n_node):
    f = open(filename)
    line = f.readline()
    tok = line.strip().split()
    n_embed = int(tok[1])
    f.close()

    embedding_matrix = np.random.rand(n_node, n_embed)
    i = -1
    with open(filename) as infile:
        for line in infile.readlines()[1:]:
            i += 1
            emd = line.strip().split()
            embedding_matrix[int(emd[0]), :] = str_list_to_float(emd[1:])
    return embedding_matrix

parser = argparse.ArgumentParser()
parser.add_argument('--datasetname', type=str, default='Amazon-Photo')
args = parser.parse_args()

datasetname = args.datasetname
path = osp.expanduser('datasets')
path = osp.join(path, datasetname)
dataset = get_dataset(path, datasetname)
data = dataset[0]

edge = data.edge_index.cpu().numpy().T
np.savetxt('temp/' + datasetname + '/n2v.input', edge, fmt='%d')
cmd = './node2vec -i:../temp/' + datasetname + '/n2v.input -o:../temp/' + datasetname + '/n2v.output -d:128 -v'
call(cmd, cwd='node2vec/', shell=True)
embedding_matrix = read_embeddings('temp/' + datasetname + '/n2v.output', data.x.shape[0])

np.save('temp/' + datasetname + '/n2vemb.npy', embedding_matrix)
