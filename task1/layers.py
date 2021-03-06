import tensorflow as tf
import numpy as np

slim = tf.contrib.slim


def conv_factory(x, hidden_num, kernel_size, stride, is_train, reuse, in_channels=None, shape_x=None):
    vs = tf.get_variable_scope()
    if shape_x is None:
        in_channels = x.get_shape()[3]
    else:
        in_channels = shape_x[3]
    W = tf.get_variable('weights', [kernel_size, kernel_size, in_channels, hidden_num],
                        initializer=tf.contrib.layers.variance_scaling_initializer())
    b = tf.get_variable('biases', [1, 1, 1, hidden_num],
                        initializer=tf.constant_initializer(0.0))

    x = tf.nn.conv2d(x, W, strides=[1, stride, stride, 1], padding='SAME')
    #  x = slim.batch_norm(x, is_training=is_train, reuse=reuse, scale=True,
    #        fused=True, scope=vs, updates_collections=None)
    x = batch_norm(x, is_train=is_train, shape_x=shape_x)
    x = tf.nn.relu(x)
    #  x = tf.nn.sigmoid(x)
    return x


def sepconv_factory(x, hidden_num, kernel_size, stride, is_train, reuse):
    # separable convolution as in MobileNet paper


    # with tf.variable_scope('dw', reuse=reuse): # not used because of legacy
    vs = tf.get_variable_scope()
    in_channels = x.get_shape()[3]
    W = tf.get_variable('weights', [kernel_size, kernel_size, in_channels, 1],
                        initializer=tf.contrib.layers.variance_scaling_initializer())
    b = tf.get_variable('biases', [1, 1, 1, in_channels],
                        initializer=tf.constant_initializer(0.0))

    x = tf.nn.depthwise_conv2d(x, W, strides=[1, stride, stride, 1], padding='SAME')
    #  x = slim.batch_norm(x, is_training=is_train, reuse=reuse, scale=True,
    #        fused=True, scope=vs, updates_collections=None)
    x = batch_norm(x, is_train=is_train)
    x = tf.nn.relu(x)

    with tf.variable_scope('1x1', reuse=reuse):
        W = tf.get_variable('weights', [1, 1, in_channels, hidden_num],
                            initializer=tf.contrib.layers.variance_scaling_initializer())
        b = tf.get_variable('biases', [1, 1, 1, hidden_num],
                            initializer=tf.constant_initializer(0.0))
        x = tf.nn.conv2d(x, W, strides=[1, 1, 1, 1], padding='SAME')
        x = batch_norm(x, is_train=is_train)
        x = tf.nn.relu(x)
    # x = tf.nn.sigmoid(x)

    return x


def resblock_factory(x, hidden_num, kernel_size, stride, is_train, reuse):
    in_channels = x.get_shape()[3]
    W = tf.get_variable('weights', [1, 1, in_channels, hidden_num],
                        initializer=tf.contrib.layers.variance_scaling_initializer())
    x1 = tf.nn.conv2d(x, W, strides=[1, 1, 1, 1], padding='SAME')
    x1 = batch_norm(x1, is_train=is_train)

    with tf.variable_scope('1', reuse=reuse):
        x2 = conv_factory(x, hidden_num, 3, 1, is_train, reuse)
    with tf.variable_scope('2', reuse=reuse):
        W = tf.get_variable('weights', [3, 3, hidden_num, hidden_num],
                            initializer=tf.contrib.layers.variance_scaling_initializer())
        x2 = tf.nn.conv2d(x2, W, strides=[1, 1, 1, 1], padding='SAME')

    with tf.variable_scope('combine', reuse=reuse):
        x = x1 + x2
        x = batch_norm(x, is_train=is_train)
    return x

def fc_factory(x, hidden_num, is_train, reuse):
    vs = tf.get_variable_scope()
    in_channels = x.get_shape()[1]
    W = tf.get_variable('weights', [in_channels, hidden_num],
                        initializer=tf.contrib.layers.variance_scaling_initializer())
    b = tf.get_variable('biases', [1, hidden_num],
                        initializer=tf.constant_initializer(0.0))

    x = tf.matmul(x, W)
    #  x = slim.batch_norm(x, is_training=is_train, reuse=reuse, scale=True,
    #        fused=True, scope=vs, updates_collections=None)
    x = batch_norm(x, is_train=is_train)
    x = tf.nn.relu(x)
    #  x = tf.nn.sigmoid(x)
    return x


def leaky_relu(x):
    alpha = 0.05
    pos = tf.nn.relu(x)
    neg = alpha * (x - abs(x)) * 0.5
    return pos + neg


def batch_norm(x, is_train=True, decay=0.99, epsilon=0.001, shape_x=None):
    if shape_x is None:
        shape_x = x.get_shape().as_list()
    beta = tf.get_variable('beta', shape_x[-1], initializer=tf.constant_initializer(0.0))
    gamma = tf.get_variable('gamma', shape_x[-1], initializer=tf.constant_initializer(1.0))
    moving_mean = tf.get_variable('moving_mean', shape_x[-1],
                                  initializer=tf.constant_initializer(0.0), trainable=False)
    moving_var = tf.get_variable('moving_var', shape_x[-1],
                                 initializer=tf.constant_initializer(1.0), trainable=False)

    if is_train:
        mean, var = tf.nn.moments(x, np.arange(len(shape_x) - 1), keep_dims=True)
        mean = tf.reshape(mean, [mean.shape.as_list()[-1]])
        var = tf.reshape(var, [var.shape.as_list()[-1]])

        update_moving_mean = tf.assign(moving_mean, moving_mean * decay + mean * (1 - decay))
        update_moving_var = tf.assign(moving_var,
                                      moving_var * decay + shape_x[0] / (shape_x[0] - 1) * var * (1 - decay))
        update_ops = [update_moving_mean, update_moving_var]

        with tf.control_dependencies(update_ops):
            return tf.nn.batch_normalization(x, mean, var, beta, gamma, epsilon)

    else:
        mean = moving_mean
        var = moving_var
        return tf.nn.batch_normalization(x, mean, var, beta, gamma, epsilon)


def smooth_l1(x):
    return tf.where(tf.less(tf.abs(x), 1), 0.5 * tf.pow(x, 2), tf.abs(x) - 0.5)
