import argparse
import os.path as osp
import random
import nni
import torch.nn.functional as F
import torch
from simple_param.sp import SimpleParam
from pGRACE.model import Encoder, GRACE
from pGRACE.functional import drop_edge_weighted, drop_feature_weighted_2
from pGRACE.eval import log_regression, MulticlassEvaluator
from pGRACE.utils import get_base_model, get_activation, generate_split, adj_mse_loss, Attention, Up_proj, motif_drop_weights
from pGRACE.dataset import get_dataset
import numpy as np

def train():
    model.train()
    encoder1.train()
    encoder2.train()
    attention1.train()
    attention2.train()
    up_proj.train()
    optimizer.zero_grad()
    optimizer1.zero_grad()
    optimizer2.zero_grad()
    optimizer_attn1.zero_grad()
    optimizer_attn2.zero_grad()
    optimizerup.zero_grad()

    def drop_edge(idx: int):
        global drop_weights
        return drop_edge_weighted(data.edge_index, drop_weights, p=param[f'drop_edge_rate_{idx}'], threshold=0.7)

    edge_index_1 = drop_edge(1)
    edge_index_2 = drop_edge(2)

    x_1 = drop_feature_weighted_2(data.x, feature_weights, param['drop_feature_rate_1'])
    x_2 = drop_feature_weighted_2(data.x, feature_weights, param['drop_feature_rate_2'])
    
    z_pseudo1 = encoder1(data.x, tedge) # tedge
    z_pseudo2 = encoder2(data.x, fedge) # fedge

    z1 = model(x_1, edge_index_1)
    z2 = model(x_2, edge_index_2)

    emb1 = torch.stack([z1, z_pseudo1], dim=1) # [n_node, 2, n_emb]
    emb2 = torch.stack([z2, z_pseudo2], dim=1)
    emb1, _ = attention1(emb1)
    emb2, _ = attention2(emb2)

    generated_G = torch.sigmoid(torch.mm(z_pseudo1, z_pseudo1.transpose(-1,-2)))
    loss_rec = adj_mse_loss(generated_G, adj_raw)
    loss = model.loss(emb1, emb2, batch_size=1024 if args.dataset == 'Coauthor-Phy' else None) + args.beta * loss_rec / data.num_nodes + args.gamma * F.mse_loss(up_proj(z_pseudo2), data.x)
    loss.backward()
    optimizer.step()
    optimizer1.step()
    optimizer2.step()
    optimizer_attn1.step()
    optimizer_attn2.step()
    optimizerup.step()
    return loss.item()

def test(final=False):
    model.eval()
    z = model(data.x, data.edge_index)

    evaluator = MulticlassEvaluator()
    if args.dataset in ['Cora', 'PubMed', 'CiteSeer']:
        acc = log_regression(z, dataset, evaluator, split='preloaded', num_epochs=3000, preload_split=split)['acc']
    else:
        acc = log_regression(z, dataset, evaluator, split='rand:0.1', num_epochs=3000, preload_split=split)['acc']

    if final and use_nni:
        nni.report_final_result(acc)
    elif use_nni:
        nni.report_intermediate_result(acc)
    return acc

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', type=str, default='cuda:0')
    parser.add_argument('--dataset', type=str, default='WikiCS')
    parser.add_argument('--param', type=str, default='local:wikics.json')
    parser.add_argument('--seed', type=int, default=39788)
    parser.add_argument('--verbose', type=str, default='train,eval,final')
    parser.add_argument('--save_split', type=str, nargs='?')
    parser.add_argument('--load_split', type=str, nargs='?')
    parser.add_argument('--beta', type=float, default=1.0)
    parser.add_argument('--gamma', type=float, default=1.0)
    parser.add_argument('--decoupled_lr', type=float, default=1e-2)
    parser.add_argument('--attn_lr', type=float, default=1e-4)
    parser.add_argument('--up_lr', type=float, default=1e-2)
    parser.add_argument('--k', type=int, default=5)
    default_param = {
        'learning_rate': 0.01,
        'num_hidden': 256,
        'num_proj_hidden': 32,
        'activation': 'prelu',
        'base_model': 'GCNConv',
        'num_layers': 2,
        'drop_edge_rate_1': 0.3,
        'drop_edge_rate_2': 0.4,
        'drop_feature_rate_1': 0.1,
        'drop_feature_rate_2': 0.0,
        'tau': 0.4,
        'num_epochs': 3000,
        'weight_decay': 1e-5,
    }

    # add hyper-parameters into parser
    param_keys = default_param.keys()
    for key in param_keys:
        parser.add_argument(f'--{key}', type=type(default_param[key]), nargs='?')
    args = parser.parse_args()

    # parse param
    sp = SimpleParam(default=default_param)
    param = sp(source=args.param, preprocess='nni')

    # merge cli arguments and parsed param
    for key in param_keys:
        if getattr(args, key) is not None:
            param[key] = getattr(args, key)

    use_nni = args.param == 'nni'
    if use_nni and args.device != 'cpu':
        args.device = 'cuda'

    torch_seed = args.seed
    torch.manual_seed(torch_seed)
    random.seed(12345)

    device = torch.device(args.device)

    path = osp.expanduser('datasets')
    path = osp.join(path, args.dataset)
    dataset = get_dataset(path, args.dataset)

    data = dataset[0]
    data = data.to(device)

    # generate split
    if args.dataset in ['Cora', 'PubMed', 'CiteSeer']:
        split = (data.train_mask, data.test_mask, data.val_mask)
    else:
        split = generate_split(data.num_nodes, train_ratio=0.1, val_ratio=0.1)

    if args.save_split:
        torch.save(split, args.save_split)
    elif args.load_split:
        split = torch.load(args.load_split)

    # encoder1 for clustering1
    encoder1 = Encoder(dataset.num_features, param['num_hidden'], get_activation(param['activation']),
                      base_model=get_base_model(param['base_model']), k=param['num_layers']).to(device)
    optimizer1 = torch.optim.Adam(encoder1.parameters(), lr=args.decoupled_lr, weight_decay=param['weight_decay'])
    
    # encoder2 for clustering2
    encoder2 = Encoder(dataset.num_features, param['num_hidden'], get_activation(param['activation']),
                      base_model=get_base_model(param['base_model']), k=param['num_layers']).to(device)
    optimizer2 = torch.optim.Adam(encoder2.parameters(), lr=args.decoupled_lr, weight_decay=param['weight_decay'])
    
    # attention between encoder1 emb and contrastive emb 1
    attention1 = Attention(param['num_hidden']).to(device)
    optimizer_attn1 = torch.optim.Adam(attention1.parameters(), lr=args.attn_lr, weight_decay=param['weight_decay'])

    # attention between encoder2 emb and contrastive emb 2
    attention2 = Attention(param['num_hidden']).to(device)
    optimizer_attn2 = torch.optim.Adam(attention2.parameters(), lr=args.attn_lr, weight_decay=param['weight_decay'])

    up_proj = Up_proj(param['num_hidden'], data.x.shape[1]).to(device)
    optimizerup = torch.optim.Adam(up_proj.parameters(), lr=args.up_lr, weight_decay=param['weight_decay'])

    # encoder for contrastive learning
    encoder = Encoder(dataset.num_features, param['num_hidden'], get_activation(param['activation']),
                      base_model=get_base_model(param['base_model']), k=param['num_layers']).to(device)
    model = GRACE(encoder, param['num_hidden'], param['num_proj_hidden'], param['tau']).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=param['learning_rate'], weight_decay=param['weight_decay'])

    # original graph structure
    adj_raw = torch.zeros(data.x.shape[0], data.x.shape[0]).to(device)
    adj_raw[data.edge_index.tolist()] = 1

    # feature based structure
    fadj = np.load('temp/' + args.dataset + '/adj_knn_' + str(args.k) +'.npy')
    fedge = torch.tensor(fadj.nonzero()).to(device)

    # topology based structure
    tadj = np.load('temp/' + args.dataset + '/adj_knn_n2v_' + str(args.k) +'.npy')
    tedge = torch.tensor(tadj.nonzero()).to(device)

    # edge augmentation
    adj = np.load('temp/' + args.dataset + '/adj.npy') 
    weights = torch.tensor(adj[data.edge_index.tolist()], device=device).to(torch.float32)
    drop_weights =  motif_drop_weights(weights)

    # random drop for motif
    feature_weights = torch.ones((data.x.size(1),)).to(device)

    log = args.verbose.split(',')

    for epoch in range(1, param['num_epochs'] + 1):
        loss = train()
        if 'train' in log:
            print(f'(T) | Epoch={epoch:03d}, loss={loss:.4f}')

        if epoch % 100 == 0:
            acc = test()

            if 'eval' in log:
                print(f'(E) | Epoch={epoch:04d}, avg_acc = {acc}')
    acc = test(final=True)

    if 'final' in log:
        print(f'{acc}')
