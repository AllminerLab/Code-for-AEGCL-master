import numpy as np
from subprocess import call
import os.path as osp
from pGRACE.dataset import get_dataset
import argparse

def convertToMaceInput(graph, node_num, out_graph_path):
    out_graph = open(out_graph_path, 'w')
    edges = [[] for i in range(node_num)]
    for line in graph:
        u = line[0]
        v = line[1]
        edges[min(u, v)].append(max(u, v))
    for l in edges:
        out_graph.write(' '.join(map(str, l)) + '\n')
    out_graph.close()

def graphMotifMatrix(edge_index, node_num, dataset):
    edge = edge_index.T.tolist()
    convertToMaceInput(edge, node_num, 'temp/' + dataset + '/mace.input')
    cmd = './mace C -l 3 -u 3 ../temp/' + dataset + '/mace.input ../temp/' + dataset + '/mace.output'
    call(cmd, cwd='mace/', shell=True)
    adj = np.zeros((node_num, node_num))
    adj[edge_index.tolist()] = 1

    with open('temp/' + dataset + '/mace.output', 'r') as f:
        for line in f:
            line = line.split()
            adj[int(line[0])][int(line[1])] += 1 
            adj[int(line[0])][int(line[2])] += 1
            adj[int(line[1])][int(line[0])] += 1
            adj[int(line[1])][int(line[2])] += 1
            adj[int(line[2])][int(line[0])] += 1
            adj[int(line[2])][int(line[1])] += 1
    np.save('temp/' + dataset + '/adj.npy',adj)

parser = argparse.ArgumentParser()
parser.add_argument('--datasetname', type=str, default='Amazon-Photo')
args = parser.parse_args()

datasetname = args.datasetname
path = osp.expanduser('datasets')
path = osp.join(path, datasetname)
dataset = get_dataset(path, datasetname)
data = dataset[0]
graphMotifMatrix(data.edge_index, data.x.shape[0], datasetname)
