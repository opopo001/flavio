from flavio.physics.running import betafunctions
from flavio.physics.running import masses
from scipy.integrate import odeint
import numpy as np
from functools import lru_cache

def rg_evolve(initial_condition, derivative, scale_in, scale_out):
    sol = odeint(derivative, initial_condition, [scale_in, scale_out])
    return sol[1]

def rg_evolve_sm(initial_condition, par, derivative_nf, scale_in, scale_out):
    if scale_in == scale_out:
        # no need to run!
        return initial_condition
    if scale_out < 0.1:
        raise ValueError('RG evolution below the strange threshold not implemented.')
    mc = par[('mass','c')]
    mb = par[('mass','b')]
    mt = par[('mass','t')]
    return _rg_evolve_sm(tuple(initial_condition), mc, mb, mt, derivative_nf, scale_in, scale_out)

@lru_cache(maxsize=32)
def _rg_evolve_sm(initial_condition, mc, mb, mt, derivative_nf, scale_in, scale_out):
    # quark mass thresholds
    thresholds = {
        3: 0.1,
        4: mc,
        5: mb,
        6: mt,
        7: np.inf,
        }
    if scale_in > scale_out: # running DOWN
        # set initial values and scales
        initial_nf = initial_condition
        scale_in_nf = scale_in
        for nf in (6,5,4,3):
            if scale_in <= thresholds[nf]:
                continue
             # run either to next threshold or to final scale, whichever is closer
            scale_stop = max(thresholds[nf], scale_out)
            sol = rg_evolve(initial_nf, derivative_nf(nf), scale_in_nf, scale_stop)
            if scale_stop == scale_out:
                return sol
            initial_nf = sol
            scale_in_nf = thresholds[nf]
    elif scale_in < scale_out: # running UP
        # set initial values and scales
        initial_nf = initial_condition
        scale_in_nf = scale_in
        for nf in (3,4,5,6):
            if nf < 6 and scale_in >= thresholds[nf+1]:
                continue
             # run either to next threshold or to final scale, whichever is closer
            scale_stop = min(thresholds[nf+1], scale_out)
            sol = rg_evolve(initial_nf, derivative_nf(nf), scale_in_nf, scale_stop)
            if scale_stop == scale_out:
                return sol
            initial_nf = sol
            scale_in_nf = thresholds[nf]
    return sol

def get_alpha(par, scale):
    r"""Get the running $\overline{\mathrm{MSbar}}$ $\alpha_s$ and $\alpha_e$
    at the specified scale.
    """
    alpha_in = [par[('alpha_s')], par[('alpha_e')]]
    scale_in = par[('mass','Z')]
    alpha_out = rg_evolve_sm(alpha_in, par, betafunctions.betafunctions_qcd_qed_nf, scale_in, scale)
    return dict(zip(('alpha_s','alpha_e'),alpha_out))
#
# @lru_cache(maxsize=32)
# def _get_alpha(as_MZ, ae_MZ, MZ, scale):
#     r"""Get the running $\overline{\mathrm{MSbar}}$ $\alpha_s$ and $\alpha_e$
#     at the specified scale.
#     """
#     alpha_in = [as_MZ, ae_MZ]
#     scale_in = MZ
#     def derivative_nf(nf):
#         return lambda x, mu: betafunctions.beta_qcd_qed(x, mu, nf)
#     alpha_out = rg_evolve_sm(alpha_in, par, derivative_nf, scale_in, scale)
#     return dict(zip(('alpha_s','alpha_e'),alpha_out))


def get_mq(par, m_in, scale_in, scale_out):
    alphas_in = get_alpha(par, scale_in)['alpha_s']
    x_in = [alphas_in, m_in]
    def derivative(x, mu, nf):
        d_alphas = betafunctions.beta_qcd_qed([x[0],0], mu, nf)[0] # only alpha_s
        d_m = masses.gamma_qcd(x[1], x[0], mu, nf)
        return [ d_alphas, d_m ]
    def derivative_nf(nf):
        return lambda x, mu: derivative(x, mu, nf)
    sol = rg_evolve_sm(x_in, par, derivative_nf, scale_in, scale_out)
    return sol[1]


def get_mb(par, scale):
    m = par[('mass','b')]
    return get_mq(par=par, m_in=m, scale_in=m, scale_out=scale)

def get_mc(par, scale):
    m = par[('mass','c')]
    return get_mq(par=par, m_in=m, scale_in=m, scale_out=scale)

def get_mu(par, scale):
    m = par[('mass','u')]
    return get_mq(par=par, m_in=m, scale_in=2.0, scale_out=scale)

def get_md(par, scale):
    m = par[('mass','d')]
    return get_mq(par=par, m_in=m, scale_in=2.0, scale_out=scale)

def get_ms(par, scale):
    m = par[('mass','s')]
    return get_mq(par=par, m_in=m, scale_in=2.0, scale_out=scale)

def get_mc_pole(par, nl=2): # for mc, default to 2-loop conversion only due to renormalon ambiguity!
    mcmc = par[('mass','c')]
    alpha_s = get_alpha(par, mcmc)['alpha_s']
    return _get_mc_pole(mcmc=mcmc, alpha_s=alpha_s, nl=nl)

# cached version
@lru_cache(maxsize=32)
def _get_mc_pole(mcmc, alpha_s, nl):
    return masses.mMS2mOS(MS=mcmc, Nf=4, asmu=alpha_s, Mu=mcmc, nl=nl)

def get_mb_pole(par, nl=2): # for mb, default to 2-loop conversion only due to renormalon ambiguity!
    mbmb = par[('mass','b')]
    alpha_s = get_alpha(par, mbmb)['alpha_s']
    return _get_mb_pole(mbmb=mbmb, alpha_s=alpha_s, nl=nl)

# cached version
@lru_cache(maxsize=32)
def _get_mb_pole(mbmb, alpha_s, nl):
    return masses.mMS2mOS(MS=mbmb, Nf=5, asmu=alpha_s, Mu=mbmb, nl=nl)

def get_mt(par, scale):
    mt_pole = par[('mass','t')]
    alpha_s = get_alpha(par, scale)['alpha_s']
    return masses.mOS2mMS(mOS=mt_pole, Nf=6, asmu=alpha_s, Mu=scale, nl=3)


def get_wilson(par, c_in, adm, scale_in, scale_out):
    r"""RG evolution of a vector of Wilson coefficients.

    In terms of the anomalous dimension matrix $\gamma$, the RGE reads
    $$\mu\frac{d}{d\mu} \vec C = \gamma^T(n_f, \alpha_s, \alpha_e) \vec C$$
    """
    alpha_in = get_alpha(par, scale_in)
    # x is (c_1, ..., c_N, alpha_s, alpha_e)
    x_in = np.append(c_in, [alpha_in['alpha_s'], alpha_in['alpha_e']])
    def derivative(x, mu, nf):
        alpha_s = x[-2]
        alpha_e = x[-1]
        c = x[:-2]
        d_alpha = betafunctions.beta_qcd_qed([alpha_s, alpha_e], mu, nf)
        d_c = np.dot(adm(nf, alpha_s, alpha_e).T, c)/mu
        return np.append(d_c, d_alpha)
    def derivative_nf(nf):
        return lambda x, mu: derivative(x, mu, nf)
    sol = rg_evolve_sm(x_in, par, derivative_nf, scale_in, scale_out)
    return sol[:-2]