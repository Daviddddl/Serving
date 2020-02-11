from __future__ import print_function

from args import parse_args
import os
import paddle.fluid as fluid
import sys
from network_conf import ctr_dnn_model_dataset

dense_feature_dim = 13

def train():
    args = parse_args()
    if not os.path.isdir(args.model_output_dir):
        os.mkdir(args.model_output_dir)
    
    dense_input = fluid.layers.data(
        name="dense_input", shape=[dense_feature_dim], dtype='float32')
    sparse_input_ids = [
        fluid.layers.data(name="C" + str(i), shape=[1], lod_level=1, dtype="int64")
        for i in range(1, 27)]
    label = fluid.layers.data(name='label', shape=[1], dtype='int64')

    predict_y, loss, auc_var, batch_auc_var = ctr_dnn_model_dataset(
        dense_input, sparse_input_ids, label,
        args.embedding_size, args.sparse_feature_dim)

    optimizer = fluid.optimizer.SGD(learning_rate=1e-4)
    optimizer.minimize(loss)

    exe = fluid.Executor(fluid.CPUPlace())
    exe.run(fluid.default_startup_program())
    dataset = fluid.DatasetFactory().create_dataset("InMemoryDataset")
    dataset.set_use_var([dense_input] + sparse_input_ids + [label])
    python_executable = "python"
    pipe_command = "{} criteo_reader.py {}".format(python_executable, args.sparse_feature_dim)
    dataset.set_pipe_command(pipe_command)
    dataset.set_batch_size(128)
    thread_num = 10
    dataset.set_thread(thread_num)
    whole_filelist = ["raw_data/part-%d" % x for x in range(len(os.listdir("raw_data")))]
    #dataset.set_filelist(whole_filelist[:(len(whole_filelist)-thread_num)])
    dataset.set_filelist(whole_filelist[:thread_num])
    dataset.load_into_memory()

    epochs = 1
    for i in range(epochs):
        exe.train_from_dataset(program=fluid.default_main_program(),
                               dataset=dataset,
                               debug=True)
        print("epoch {} finished".format(i))

    import paddle_serving_client.io as server_io
    feed_var_dict = {}
    for i, sparse in enumerate(sparse_input_ids):
        feed_var_dict["sparse_{}".format(i)] = sparse
    feed_var_dict["dense_0"] = dense_input
    fetch_var_dict = {"prob": predict_y}

    server_io.save_model(
        "ctr_serving_model", "ctr_client_conf",
        feed_var_dict, fetch_var_dict, fluid.default_main_program())

if __name__ == '__main__':
    train()