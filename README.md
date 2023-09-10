## Towards Effective and Robust Graph Contrastive Learning with Graph Autoencoding



### get edge weight based on motif centrality

`python get_motif_adj.py --datasetname Amazon-Photo`

get `adj.npy` in `temp/Amazon-Photo/`



### get knn on raw features 

`python knn.py --datasetname Amazon-Photo --k 5`

get `adj_knn_5.npy` in `temp/Amazon-Photo/`



### get node2vec embedding

`python get_n2v_emb.py --datasetname Amazon-Photo`

get `n2vemb.npy` in `temp/Amazon-Photo/`



### get knn on node2vec embeddings  

`python knn_n2v.py --datasetname Amazon-Photo --k 5`

get `adj_knn_n2v_5.npy` in `temp/Amazon-Photo/`



### train AEGCL

`python train.py --device cuda:0 --dataset Amazon-Photo --param local:amazon_photo.json`



Feel free to replace `Amazon-Photo` to other datasets.

Reference:

Wen-Zhi Li, Chang-Dong Wang, Jian-Huang Lai, Philip S. Yu. "Towards Effective and Robust Graph Contrastive Learning with Graph Autoencoding", TKDE2023.
