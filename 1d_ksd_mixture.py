import tensorflow as tf
from tensorflow.python import debug as tf_debug
import numpy as np
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt
import plotly.plotly as py  # tools to communicate with Plotly's server
import os

DIR = os.getcwd() + "/output/"
EXP = "1d_mixture_ksd_temp"
EXP_DIR = DIR + EXP + "/"
if not os.path.exists(EXP_DIR):
    os.makedirs(EXP_DIR)

mb_size = 1000
X_dim = 1  # dimension of the target distribution, 3 for e.g.
z_dim = 1
h_dim_g = 50
h_dim_d = 50
N, n_D, n_G = 1000, 20, 1  # num of iterations


mu1 = 10.
mu2 = -10.

Sigma1 = 1.
Sigma2 = 1.
Sigma1_inv = 1./Sigma1
Sigma2_inv = 1./Sigma2
Sigma1_det = 1.
Sigma2_det = 1.

p1 = 0.5
p2 = 0.5

################################################################################################
################################################################################################


def output_matrix(prefix, matrix):
    if type(matrix) == int or type(matrix) == float:
        return prefix + '{}'.format(matrix)
    else:
        return prefix + matrix.__str__().replace('\n', '\n\t'+' '*len(prefix))


info = open(EXP_DIR + "_info.txt", 'w')
info.write("Description: " + '\n' +
           "KSD training"
           '\n\n' + ("=" * 80 + '\n') * 3 + '\n' +
           "Model Parameters: \n\t" +
           "\n\t".join(['mu1 = {}'.format(mu1), output_matrix('sigma1 = {}', Sigma1)]) +
           '\n\n' + ("=" * 80 + '\n') * 3 + '\n' +
           "Network Parameters: \n\t" +
           "\n\t".join(['mb_size = {}'.format(mb_size), 'X_dim = {}'.format(X_dim), 'z_dim = {}'.format(z_dim),
                        'h_dim_g = {}'.format(h_dim_g), 'h_dim_d = {}'.format(h_dim_d), 'n_D = {}'.format(n_D),
                        'n_G = {}'.format(n_G)]) +
           '\n\n' + ("=" * 80 + '\n') * 3 + '\n' +
           "Training iter: \n\t" +
           "\n\t".join(['n_D = {}'.format(n_D), 'n_G = {}'.format(n_G)]) +
           '\n\n' + ("=" * 80 + '\n') * 3 + '\n'
           "Additional Information: \n" +
           "" + "\n")
info.close()


################################################################################################
# show samples from target
show_size = 300
label = np.random.choice([0, 1], size=show_size, p=[p1, p2])
true_sample = (np.random.normal(mu1, Sigma1, show_size) * (1 - label) +
               np.random.normal(mu2, Sigma2, show_size) * label)
plt.scatter(true_sample, np.zeros(show_size), color='b', alpha=0.2, s=10)
plt.axvline(x=mu1)
plt.axvline(x=mu2)
plt.title("One sample from the target distribution")
plt.savefig(EXP_DIR + "_target_sample.png", format="png")
plt.close()
################################################################################################
# convert parameters to tf tensor
mu1_tf = tf.reshape(tf.convert_to_tensor(mu1, dtype=tf.float32), shape=[1])
mu2_tf = tf.reshape(tf.convert_to_tensor(mu2, dtype=tf.float32), shape=[1])

Sigma1_inv_tf = tf.reshape(tf.convert_to_tensor(Sigma1_inv, dtype=tf.float32), shape=[1, 1])
Sigma2_inv_tf = tf.reshape(tf.convert_to_tensor(Sigma2_inv, dtype=tf.float32), shape=[1, 1])

X = tf.placeholder(tf.float32, shape=[None, X_dim])

initializer = tf.contrib.layers.xavier_initializer()

D_W1 = tf.get_variable('D_w1', [X_dim, h_dim_d], dtype=tf.float32, initializer=initializer)
D_b1 = tf.get_variable('D_b1', [h_dim_d], initializer=initializer)
D_W2 = tf.get_variable('D_w2', [h_dim_d, h_dim_d], dtype=tf.float32, initializer=initializer)
D_b2 = tf.get_variable('D_b2', [h_dim_d], initializer=initializer)
D_W3 = tf.get_variable('D_w3', [h_dim_d, X_dim], dtype=tf.float32, initializer=initializer)
D_b3 = tf.get_variable('D_b3', [X_dim], initializer=initializer)


theta_D = [D_W1, D_W2, D_W3, D_b1, D_b2, D_b3]


z = tf.placeholder(tf.float32, shape=[None, z_dim])

G_W1 = tf.get_variable('g_w1', [z_dim, h_dim_g], dtype=tf.float32, initializer=initializer)
G_b1 = tf.get_variable('g_b1', [h_dim_g], initializer=initializer)

G_W2 = tf.get_variable('g_w2', [h_dim_g, h_dim_g], dtype=tf.float32, initializer=initializer)
G_b2 = tf.get_variable('g_b2', [h_dim_g], initializer=initializer)

G_W3 = tf.get_variable('g_w3', [h_dim_g, X_dim], dtype=tf.float32, initializer=initializer)
G_b3 = tf.get_variable('g_b3', [X_dim], initializer=initializer)

theta_G = [G_W1, G_b1, G_W2, G_b2, G_W3, G_b3]


def log_densities(xs):
    log_den1 = - tf.diag_part(tf.matmul(tf.matmul(xs - mu1_tf, Sigma1_inv_tf),
                                        tf.transpose(xs - mu1_tf))) / 2
    log_den2 = - tf.diag_part(tf.matmul(tf.matmul(xs - mu2_tf, Sigma2_inv_tf),
                                        tf.transpose(xs - mu2_tf))) / 2
    return tf.expand_dims(tf.reduce_logsumexp(tf.stack([np.log(p1) + log_den1,
                                                        np.log(p2) + log_den2], 0), 0), 1)


def S_q(xs):
    # return tf.matmul(mu_tf - x, Sigma_inv_tf)
    return tf.gradients(log_densities(xs), xs)[0]


def sample_z(m, n):
    # np.random.seed(1)
    return np.random.normal(0, 1, size=[m, n])


def generator(z):
    G_h1 = tf.nn.relu(tf.matmul(z, G_W1) + G_b1)
    G_h2 = tf.nn.relu(tf.matmul(G_h1, G_W2) + G_b2)
    out = tf.matmul(G_h2, G_W3) + G_b3
    return out


# output dimension of this function is X_dim
def discriminator(x):
    D_h1 = tf.nn.relu(tf.matmul(x, D_W1) + D_b1)
    D_h2 = tf.nn.relu(tf.matmul(D_h1, D_W2) + D_b2)
    # D_h1 = tf.Print(D_h1, [D_h1], message="Discriminator-"+"D_h1"+"-values:")
    out = (tf.matmul(D_h2, D_W3) + D_b3)
    # out = tf.Print(out, [out], message="Discriminator-"+"out"+"-values:")
    return out


def svgd_kernel(x, dim=X_dim, h=1.):
    # Reference 1: https://github.com/ChunyuanLI/SVGD/blob/master/demo_svgd.ipynb
    # Reference 2: https://github.com/yc14600/svgd/blob/master/svgd.py
    XY = tf.matmul(x, tf.transpose(x))
    X2_ = tf.reshape(tf.reduce_sum(tf.square(x), axis=1), shape=[tf.shape(x)[0], 1])
    X2 = tf.tile(X2_, [1, tf.shape(x)[0]])
    pdist = tf.subtract(tf.add(X2, tf.transpose(X2)), 2 * XY)  # pairwise distance matrix

    kxy = tf.exp(- pdist / h ** 2 / 2.0)  # kernel matrix

    sum_kxy = tf.expand_dims(tf.reduce_sum(kxy, axis=1), 1)
    dxkxy = tf.add(-tf.matmul(kxy, x), tf.multiply(x, sum_kxy)) / (h ** 2)  # sum_y dk(x, y)/dx

    dxykxy_tr = tf.multiply((dim * (h**2) - pdist), kxy)  # tr( dk(x, y)/dxdy )

    return kxy, dxkxy, dxykxy_tr


def ksd_emp(x, n=mb_size, dim=X_dim, h=1.):  # credit goes to Hanxi!!! ;P
    sq = S_q(x)
    kxy, dxkxy, dxykxy_tr = svgd_kernel(x, dim, h)
    t13 = tf.multiply(tf.matmul(sq, tf.transpose(sq)), kxy) + dxykxy_tr
    t2 = 2 * tf.trace(tf.matmul(sq, tf.transpose(dxkxy)))
    # ksd = (tf.reduce_sum(t13) - tf.trace(t13) + t2) / (n * (n-1))
    ksd = (tf.reduce_sum(t13) + t2) / (n * n)

    phi = (tf.matmul(kxy, sq) + dxkxy) / n

    return ksd, phi


def phi_func(y, x, h=1.):
    """
    This function evaluates the optimal phi from KSD at any point
    :param y: evaluate phi at y, dimension m * d
    :param x: data set used to calculate empirical expectation, dimension n*d
    :param h: the parameter in kernel function
    :return: the value of dimension m * d
    """
    m = tf.shape(y)[0]
    n = tf.shape(x)[0]
    XY = tf.matmul(y, tf.transpose(x))
    X2_ = tf.reshape(tf.reduce_sum(tf.square(x), axis=1), shape=[n, 1])
    X2 = tf.tile(X2_, [1, m])
    Y2_ = tf.reshape(tf.reduce_sum(tf.square(y), axis=1), shape=[m, 1])
    Y2 = tf.tile(Y2_, [1, n])
    pdist = tf.subtract(tf.add(Y2, tf.transpose(X2)), 2 * XY)  # pairwise distance matrix

    kxy = tf.exp(- pdist / h ** 2 / 2.0)  # kernel matrix

    sum_kxy = tf.expand_dims(tf.reduce_sum(kxy, axis=1), 1)
    dxkxy = tf.add(-tf.matmul(kxy, x), tf.multiply(y, sum_kxy)) / (h ** 2)  # sum_y dk(x, y)/dx

    phi = (tf.matmul(kxy, S_q(x)) + dxkxy) / mb_size

    return phi


def diag_gradient(y, x):
    dg = tf.stack([tf.gradients(y[:, i], x)[0][:, i] for i in range(X_dim)], axis=0)
    return tf.transpose(dg)


G_sample = generator(z)

ksd, D_fake_ksd = ksd_emp(G_sample)

D_fake = discriminator(G_sample)
G_sample_fake_fake =(G_sample - tf.reduce_mean(G_sample))*2 + tf.reduce_mean(G_sample)
D_fake_fake = discriminator(G_sample_fake_fake)

norm_S = tf.sqrt(tf.reduce_mean(tf.square(D_fake_fake)))


# sess = tf.Session()
# sess.run(tf.global_variables_initializer())
# x, f, p = sess.run([G_sample, D_fake, phi_y], feed_dict={z: sample_z(mb_size, z_dim)})
# print(f)
# print(p)


range_penalty_g = 10*(generator(tf.constant(1, shape=[1, 1], dtype=tf.float32)) -
                      generator(tf.constant(-1, shape=[1, 1], dtype=tf.float32)))
# range_penalty_g = tf.Print(range_penalty_g, [range_penalty_g], message="range_penalty_g"+"-values:")


loss1 = tf.expand_dims(tf.reduce_sum(tf.multiply(S_q(G_sample), D_fake), 1), 1)
loss2 = tf.expand_dims(tf.reduce_sum(diag_gradient(D_fake, G_sample), axis=1), 1)

Loss = tf.abs(tf.reduce_mean(loss1 + loss2))/norm_S


D_solver = (tf.train.GradientDescentOptimizer(learning_rate=1e-2)
            .minimize(-Loss, var_list=theta_D))

G_solver = (tf.train.GradientDescentOptimizer(learning_rate=1e-2).minimize(Loss, var_list=theta_G))

# G_solver_ksd = (tf.train.GradientDescentOptimizer(learning_rate=1e-1).minimize(ksd, var_list=theta_G))
G_solver_ksd = (tf.train.GradientDescentOptimizer(learning_rate=1e-2).minimize(ksd, var_list=theta_G))


#######################################################################################################################
#######################################################################################################################

sess = tf.Session()
sess.run(tf.global_variables_initializer())


ksd_loss = np.zeros(N)

ksd_curr = None

for it in range(N):

    _, ksd_curr = sess.run([G_solver_ksd, ksd], feed_dict={z: sample_z(mb_size, z_dim)})

    ksd_loss[it] = ksd_curr

    if it % 10 == 0:
        noise = sample_z(show_size, 1)
        z_range = np.reshape(np.linspace(-5, 5, 500, dtype=np.float32), newshape=[500, 1])

        samples = sess.run(generator(noise.astype(np.float32)))
        gen_func = sess.run(generator(z_range))
        sample_mean = np.mean(samples)
        sample_sd = np.std(samples)
        print(it, ":", sample_mean, sample_sd)
        print("ksd_loss:", ksd_curr)

        # print("w:", G_W1.eval(session=sess), "b:", G_b1.eval(session=sess))
        # plt.scatter(samples[:, 0], samples[:, 1], color='b')
        # plt.scatter([mu1[0], mu2[0]], [mu1[1], mu2[1]], color="r")

        plt.plot(figsize=(100, 100))
        plt.subplot(222)
        plt.title("Histogram")
        num_bins = 100
        # the histogram of the data
        n, bins, patches = plt.hist(samples, num_bins, normed=1, facecolor='green', alpha=0.5)
        # add a 'best fit' line
        y = p1 * mlab.normpdf(bins, mu1, Sigma1) + p2 * mlab.normpdf(bins, mu2, Sigma2)
        plt.plot(bins, y, 'r--')
        plt.ylabel('Probability')
        # # Tweak spacing to prevent clipping of ylabel
        # plt.subplots_adjust(left=0.15)
        #
        # plot_url = py.plot_mpl(fig, filename='docs/histogram-mpl-legend')

        plt.subplot(224)
        plt.title("Generator")
        plt.plot(z_range, gen_func)
        plt.axhline(y=0, color="y")

        plt.subplot(223)
        plt.title("vs true")
        bins = np.linspace(-mu1-2, mu1+2, 100)
        plt.hist(true_sample, bins, alpha=0.5, color="purple")
        plt.hist(samples, bins, alpha=0.5, color="green")

        plt.subplot(221)
        plt.title("Samples")
        plt.scatter(true_sample, np.ones(show_size), color='purple', alpha=0.2, s=10)
        plt.scatter(samples[:, 0], np.zeros(show_size), color='b', alpha=0.2, s=10)
        plt.axvline(mu1, color='r')
        plt.axvline(mu2, color='r')
        plt.title(
            "iter {0:04d}, {{ksd: {1:.4f}}}".format(it, ksd_curr))
        plt.savefig(EXP_DIR + "iter {0:04d}".format(it))
        plt.close()

sess.close()


np.savetxt(EXP_DIR + "_loss_ksd.csv", ksd_loss, delimiter=",")
plt.plot(ksd_loss)
plt.ylim(ymin=0)
plt.axvline(np.argmin(ksd_loss), ymax=np.min(ksd_loss), color="r")
plt.title("KSD (min at iter {})".format(np.argmin(ksd_loss)))
plt.savefig(EXP_DIR + "_ksd.png", format="png")
plt.close()

# np.savetxt(EXP_DIR + "_w.csv", w, delimiter=",")
# plt.plot(w)
# plt.ylim(-Sigma1-1, Sigma1 + 1)
# plt.axhline(y=Sigma1, color="r")
# plt.axhline(y=-Sigma1, color="r")
# plt.title("Weight")
# plt.savefig(EXP_DIR + "_W.png", format="png")
# plt.close()
#
# np.savetxt(EXP_DIR + "_b.csv", b, delimiter=",")
# plt.plot(b)
# plt.ylim(mu1-1, mu1 + 1)
# plt.axhline(y=mu1, color="r")
# plt.title("Bias")
# plt.savefig(EXP_DIR + "_B.png", format="png")
# plt.close()
