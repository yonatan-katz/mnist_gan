from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import os
RESEARCH_FOLDER='/home/yonic/repos/models/research/'
sys.path.append(os.path.join(RESEARCH_FOLDER))
sys.path.append(os.path.join(RESEARCH_FOLDER,'gan'))
sys.path.append(os.path.join(RESEARCH_FOLDER,'slim'))

import matplotlib.pyplot as plt
import numpy as np
import time
import functools
from six.moves import xrange  # pylint: disable=redefined-builtin

import tensorflow as tf

# Main TFGAN library.
tfgan = tf.contrib.gan

# TFGAN MNIST examples from `tensorflow/models`.
from mnist import data_provider
from mnist import util

# TF-Slim data provider.
from datasets import download_and_convert_mnist

# Shortcuts for later.
queues = tf.contrib.slim.queues
layers = tf.contrib.layers
ds = tf.contrib.distributions
framework = tf.contrib.framework

leaky_relu = lambda net: tf.nn.leaky_relu(net, alpha=0.01)
noise_dims = 64

def generator_fn(noise, weight_decay=2.5e-5, is_training=True):
    """Simple generator to produce MNIST images.

    Args:
        noise: A single Tensor representing noise.
        weight_decay: The value of the l2 weight decay.
        is_training: If `True`, batch norm uses batch statistics. If `False`, batch
            norm uses the exponential moving average collected from population 
            statistics.

    Returns:
        A generated image in the range [-1, 1].
    """
    with framework.arg_scope(
        [layers.fully_connected, layers.conv2d_transpose],
        activation_fn=tf.nn.relu, normalizer_fn=layers.batch_norm,
        weights_regularizer=layers.l2_regularizer(weight_decay)),\
            framework.arg_scope([layers.batch_norm], is_training=is_training,
                        zero_debias_moving_mean=True):
        net = layers.fully_connected(noise, 1024)
        net = layers.fully_connected(net, 7 * 7 * 256)
        net = tf.reshape(net, [-1, 7, 7, 256])
        net = layers.conv2d_transpose(net, 64, [4, 4], stride=2)
        net = layers.conv2d_transpose(net, 32, [4, 4], stride=2)
        # Make sure that generator output is in the same range as `inputs`
        # ie [-1, 1].
        net = layers.conv2d(net, 1, 4, normalizer_fn=None, activation_fn=tf.tanh)

        return net

# ### Discriminator
def discriminator_fn(img, unused_conditioning, weight_decay=2.5e-5,
                         is_training=True):
    """Discriminator network on MNIST digits.

    Args:
        img: Real or generated MNIST digits. Should be in the range [-1, 1].
        unused_conditioning: The TFGAN API can help with conditional GANs, which
            would require extra `condition` information to both the generator and the
            discriminator. Since this example is not conditional, we do not use this
            argument.
        weight_decay: The L2 weight decay.
        is_training: If `True`, batch norm uses batch statistics. If `False`, batch
            norm uses the exponential moving average collected from population 
            statistics.

    Returns:
        Logits for the probability that the image is real.
    """
    with framework.arg_scope(
        [layers.conv2d, layers.fully_connected],
        activation_fn=leaky_relu, normalizer_fn=None,
        weights_regularizer=layers.l2_regularizer(weight_decay),
        biases_regularizer=layers.l2_regularizer(weight_decay)):
        net = layers.conv2d(img, 64, [4, 4], stride=2)
        net = layers.conv2d(net, 128, [4, 4], stride=2)
        net = layers.flatten(net)
        with framework.arg_scope([layers.batch_norm], is_training=is_training):
            net = layers.fully_connected(net, 1024, normalizer_fn=layers.batch_norm)
        return layers.linear(net, 1)
 
def visualize_training_generator(train_step_num, start_time, data_np):
    """Visualize generator outputs during training.
    
    Args:
        train_step_num: The training step number. A python integer.
        start_time: Time when training started. The output of `time.time()`. A
            python float.
        data: Data to plot. A numpy array, most likely from an evaluated TensorFlow
            tensor.
    """
    print('Training step: %i' % train_step_num)
    time_since_start = (time.time() - start_time) / 60.0
    print('Time since start: %f m' % time_since_start)
    print('Steps per min: %f' % (train_step_num / time_since_start))
    plt.axis('off')
    plt.imshow(np.squeeze(data_np), cmap='gray')
    plt.show()


def visualize_digits(tensor_to_visualize):
    """Visualize an image once. Used to visualize generator before training.
    
    Args:
        tensor_to_visualize: An image tensor to visualize. A python Tensor.
    """
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        with queues.QueueRunners(sess):
            images_np = sess.run(tensor_to_visualize)
    plt.axis('off')
    plt.imshow(np.squeeze(images_np), cmap='gray')

def evaluate_tfgan_loss(gan_loss, name=None):
    """Evaluate GAN losses. Used to check that the graph is correct.
    
    Args:
        gan_loss: A GANLoss tuple.
        name: Optional. If present, append to debug output.
    """
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        with queues.QueueRunners(sess):
            gen_loss_np = sess.run(gan_loss.generator_loss)
            dis_loss_np = sess.run(gan_loss.discriminator_loss)
    if name:
        print('%s generator loss: %f' % (name, gen_loss_np))
        print('%s discriminator loss: %f'% (name, dis_loss_np))
    else:
        print('Generator loss: %f' % gen_loss_np)
        print('Discriminator loss: %f'% dis_loss_np)


MNIST_DATA_DIR = '/home/yonic/repos/mnist_gan/mnist-data'

def train(is_train):
    
    if not tf.gfile.Exists(MNIST_DATA_DIR):
        tf.gfile.MakeDirs(MNIST_DATA_DIR)
    
    #download_and_convert_mnist.run(MNIST_DATA_DIR)
    
    tf.reset_default_graph()
    
    # Define our input pipeline. Pin it to the CPU so that the GPU can be reserved
    # for forward and backwards propogation.
    batch_size = 32
    with tf.device('/cpu:0'):
        real_images, _, _ = data_provider.provide_data(
            'train', batch_size, MNIST_DATA_DIR)
    
    # Sanity check that we're getting images.
    #check_real_digits = tfgan.eval.image_reshaper(
    #    real_images[:20,...], num_cols=10)
    #print('visualize_digits')
    #visualize_digits(check_real_digits)
    #plt.show()    
    
    gan_model = tfgan.gan_model(
        generator_fn,
        discriminator_fn,
        real_data=real_images,
        generator_inputs=tf.random_normal([batch_size, noise_dims]))
    
    improved_wgan_loss = tfgan.gan_loss(
        gan_model,
        # We make the loss explicit for demonstration, even though the default is 
        # Wasserstein loss.
        generator_loss_fn=tfgan.losses.wasserstein_generator_loss,
        discriminator_loss_fn=tfgan.losses.wasserstein_discriminator_loss,
        gradient_penalty_weight=1.0)
    
    # Sanity check that we can evaluate our losses.
    print("Sanity check that we can evaluate our losses")
    for gan_loss, name in [(improved_wgan_loss, 'improved wgan loss')]:
        evaluate_tfgan_loss(gan_loss, name)
    
    
    #generator_optimizer = tf.train.AdamOptimizer(0.001, beta1=0.5)
    #discriminator_optimizer = tf.train.AdamOptimizer(0.0001, beta1=0.5)
    generator_optimizer = tf.train.RMSPropOptimizer(0.001)
    discriminator_optimizer = tf.train.RMSPropOptimizer(0.0001)
    gan_train_ops = tfgan.gan_train_ops(
        gan_model,
        improved_wgan_loss,
        generator_optimizer,
        discriminator_optimizer)
    
    # ### Evaluation
    
    num_images_to_eval = 500
    MNIST_CLASSIFIER_FROZEN_GRAPH = os.path.join(
            RESEARCH_FOLDER,
            'gan/mnist/data/classify_mnist_graph_def.pb')
    
    # For variables to load, use the same variable scope as in the train job.
    with tf.variable_scope('Generator', reuse=True):
        eval_images = gan_model.generator_fn(
            tf.random_normal([num_images_to_eval, noise_dims]),
            is_training=False)
    
    # Calculate Inception score.
    eval_score = util.mnist_score(eval_images, MNIST_CLASSIFIER_FROZEN_GRAPH)
    
    # Calculate Frechet Inception distance.
    with tf.device('/cpu:0'):
        real_images, _, _ = data_provider.provide_data(
            'train', num_images_to_eval, MNIST_DATA_DIR)
    frechet_distance = util.mnist_frechet_distance(
        real_images, eval_images, MNIST_CLASSIFIER_FROZEN_GRAPH)
    
    # Reshape eval images for viewing.
    generated_data_to_visualize = tfgan.eval.image_reshaper(
        eval_images[:20,...], num_cols=10)
    
     # This code block should take about **1 minute** to run on a GPU kernel, and about **8 minutes** on CPU.
    
    train_step_fn = tfgan.get_sequential_train_steps()
    
    global_step = tf.train.get_or_create_global_step()
    loss_values, mnist_scores, frechet_distances  = [], [], []
    tf.summary.scalar('dis_loss', gan_loss.discriminator_loss)
    tf.summary.scalar('gen_loss', gan_loss.generator_loss)
    merged = tf.summary.merge_all()
    saver = tf.train.Saver()
    saver_hook =  tf.train.CheckpointSaverHook(
      checkpoint_dir= "./models",
      save_steps=1000,
      saver=saver)
     
    print("Graph trainable nodes:")
    for v in tf.trainable_variables():
        print (v.name)
   
    with tf.train.SingularMonitoredSession(hooks=[saver_hook],
        checkpoint_dir="./models") as sess:
        start_time = time.time()
        train_writer = tf.summary.FileWriter("./summary", sess.graph)
        if is_train:
            for i in xrange(2000):
                cur_loss, _ = train_step_fn(
                    sess, gan_train_ops, global_step, train_step_kwargs={})
                loss_values.append((i, cur_loss))

                if i % 10 == 0:
                    merged_val = sess.run(merged)
                    train_writer.add_summary(merged_val, i)
                    print("Step:{}".format(i))

            mnist_score, f_distance, digits_np = sess.run(
                [eval_score, frechet_distance, generated_data_to_visualize])
            mnist_scores.append((i, mnist_score))
            frechet_distances.append((i, f_distance))
            print('Current loss: %f' % cur_loss)
            print('Current MNIST score: %f' % mnist_scores[-1][1])
            print('Current Frechet distance: %f' % frechet_distances[-1][1])
            visualize_training_generator(i, start_time, digits_np)
            
        else: #generate from trained model
            generated = sess.run(eval_images)
            print("generated[0] shape:{}".format(generated[0].shape))
            plt.imshow(np.squeeze(generated[0]), cmap='gray')
            plt.show()
            
        
    
    


if __name__ == '__main__':
    train(False)