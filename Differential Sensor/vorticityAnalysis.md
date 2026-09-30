# Predicting Vortex-Shedding Frequency and Building a Sample Pressure Sinusoid

**Measured** values come from the experiment. **Assumed** values come from textbooks or experimental data from other studies.

---

## 1. Strouhal number

```math
St = \frac{f\,D}{U}
```

| Symbol | Meaning | Units | Role |
|---|---|---|---|
| $f$ | Shedding frequency | Hz | Input |
| $D$ | Cylinder diameter | m | Input |
| $U$ | Flow speed | m/s | Input |
| $St$ | Strouhal number | – | Output |

$f$ is unknown before the test, so $St$ has to be estimated from experimental data. For $300 < Re < 2\times10^{5}$, the code **assumes**:

```math
St = 0.20
```

---

## 2. Shedding frequency

```math
f = \frac{St\,U}{D}
```

| Symbol | Meaning | Units | Value | Source |
|---|---|---|---|---|
| $St$ | Strouhal number | – | 0.20 | Assumed |
| $U$ | Flow speed | m/s | 0.4 | Measured |
| $D$ | Cylinder diameter | m | 0.033 | Measured |
| $f$ | Shedding frequency | Hz | – | Output |

```math
f = \frac{0.20 \times 0.4}{0.033} \approx 2.42\ \text{Hz}
```

---

## 3. Sample sinusoid

```math
p(t) = \bar{p} + A\,\sin(2\pi f t + \phi)
```

| Symbol | Meaning | Units |
|---|---|---|
| $p(t)$ | Simulated pressure | kPa |
| $\bar{p}$ | Mean pressure | kPa |
| $A$ | Amplitude | kPa |
| $f$ | Frequency | Hz |
| $t$ | Time | s |
| $\phi$ | Phase | rad |

### Choosing each term

**1. Mean pressure, $\bar{p}$ (measured):** the average of the measured sensor channel.

```math
\bar{p} = \frac{1}{N}\sum_{n=0}^{N-1} p_n
```

**2. Amplitude, $A$ (assumed):** with $\rho = 998\ \text{kg/m}^3$ and $C'_p = 0.05$:

```math
A = C'_p\left(\tfrac{1}{2}\rho U^{2}\right)
```

```math
A = 0.05 \times \left(\tfrac{1}{2} \times 998 \times 0.4^{2}\right) = 3.99\ \text{Pa} = 0.00399\ \text{kPa}
```

**3. Phase, $\phi$ (assumed):**

```math
\phi = 0
```

**4. Sampling rate, $f_s$ (measured):** from the data's timestamps.

```math
f_s = \frac{1}{\Delta t}
```

**5. Timestamps, $t_n$ (measured):** the sensor's own times.

```math
t_n = t_0 + \frac{n}{f_s}, \qquad n = 0, 1, 2, \dots
```

### Result

```math
p(t) = \bar{p} + 0.00399\,\sin(2\pi \cdot 2.42\,t) \quad [\text{kPa}]
```