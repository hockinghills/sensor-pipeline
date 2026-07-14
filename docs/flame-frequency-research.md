# Flame Frequency Analysis Research
## Combustion Dynamics for Art Glass Furnace Monitoring

**November 2025 — Lyon's Pyre Glasswerks**

---

## Executive Summary

This research document identifies the characteristic frequency domains present in combustion systems and provides sampling recommendations for flame sensor instrumentation. The goal is to answer: "What frequencies matter in combustion analysis?" so that your ESP32-S3 ADC sampling can be configured optimally—neither too slow (missing dynamics) nor too fast (drowning in noise).

**Key Finding:** For a propane-fired recuperated pot furnace, the primary frequencies of interest range from approximately 1 Hz to 1000 Hz, with the most critical dynamics occurring in two bands:

- **Flame flicker (1–20 Hz):** Visible oscillation driven by buoyancy and turbulence
- **Thermoacoustic oscillations (30–500 Hz):** Acoustic coupling between heat release and furnace geometry

**Recommended minimum sample rate: 2 kHz.** This captures the full range of combustion dynamics with adequate Nyquist margin. For detailed analysis, 10 kHz provides excellent frequency resolution while remaining manageable for data storage.

---

## 1. Combustion Frequency Domains

Combustion systems exhibit oscillations across multiple frequency bands, each with distinct physical causes and implications for furnace operation.

### Summary Table

| Phenomenon | Frequency Range | Physical Cause | What It Indicates |
|------------|-----------------|----------------|-------------------|
| **Flame Flicker** | 1–20 Hz | Buoyancy-driven oscillation of flame front; toroidal vortex formation at ~10 Hz independent of fuel type | Normal combustion; used by commercial flame detectors |
| **Thermoacoustic Oscillations** | 30–500 Hz | Coupling between heat release fluctuations and acoustic modes of combustion chamber (Rayleigh criterion) | Potential instability; "rumble" if severe |
| **Burner Instability / Flame Lift** | 30–100 Hz | Flame detachment from burner; interaction with upstream air supply dynamics | Dangerous condition; needs correction |
| **Combustion Chamber Pressure** | 50–1000 Hz | Acoustic modes determined by furnace geometry; Helmholtz resonances | Characteristic of specific furnace design |
| **Turbulent Flame Dynamics** | Broadband (noise) | Random turbulent fluctuations in flame structure; "combustion noise" | Background signal; changes indicate combustion quality |
| **Fuel-Air Ratio Variations** | <10 Hz | Slow variations in equivalence ratio; atmospheric pressure changes; proportionator valve response | Monitor for optimization; affects efficiency |

### 1.1 Flame Flicker (1–20 Hz)

Flame flicker is the most visually obvious combustion oscillation. Research consistently shows this phenomenon occurs at approximately **10 Hz independent of fuel type or burner design**. This frequency is driven by buoyancy—gravity causes hot combustion gases to rise, creating periodic vortex structures at the flame base.

**Key research findings:**

- Diffusion flames (ethylene, methane, propane) oscillate at 10–20 Hz with toroidal vortex convective velocity of ~0.8 m/s
- Photodiode studies at 10 kHz sample rate found frequency peaks at 9–10 Hz for premixed surface burners
- Commercial flame detectors use the 1–20 Hz flicker band to distinguish real flames from hot surfaces
- Sawtooth waveform characteristic: slow intensity rise followed by rapid collapse as vortex sheds

**Monitoring value:** Flicker amplitude and regularity indicate flame stability. Irregular flicker patterns may precede instability events.

### 1.2 Thermoacoustic Oscillations (30–500 Hz)

Thermoacoustic oscillations occur when heat release fluctuations couple constructively with acoustic pressure waves in the combustion chamber. This is governed by the *Rayleigh criterion*: instability grows when pressure and heat release oscillate in phase.

**Frequency determinants:**

- Combustion chamber geometry (length, volume, shape)
- Temperature gradient between inlet air and hot gases
- Burner inlet configuration and ducting
- Fuel composition and equivalence ratio

A 2017 Babcock & Wilcox study of an industrial natural gas boiler found a dominant oscillation at **10 Hz with sharp harmonics** during rumble conditions. The presence of time-asymmetric (sawtooth) waveforms confirmed thermoacoustic rather than flow-induced origin.

**Monitoring value:** Emergence of sharp spectral peaks with harmonics indicates developing instability. Modern research uses precursor detection algorithms that can predict instability onset 100–500 ms in advance.

### 1.3 Context for Glass Furnace Application

For a propane-fired recuperated pot furnace operating at 2300°F, the relevant frequency bands are likely:

1. **Primary flicker:** 8–12 Hz (buoyancy-driven, characteristic of propane diffusion flames)
2. **Thermoacoustic modes:** Dependent on your specific furnace geometry; likely 20–200 Hz range
3. **Atmospheric effects:** <1 Hz (barometric pressure changes affecting combustion efficiency)
4. **Proportionator response:** <5 Hz (control valve dynamics)

---

## 2. Sampling Recommendations

### 2.1 Nyquist Analysis

The Nyquist theorem requires sampling at ≥2× the highest frequency of interest. However, practical implementations typically use 5–10× to ensure adequate frequency resolution and avoid aliasing artifacts.

| Target Frequency | Minimum Sample Rate | Recommended Rate | Use Case | Data Rate (12-bit) |
|------------------|---------------------|------------------|----------|-------------------|
| Flame flicker only (20 Hz) | 40 Hz | 100–200 Hz | Basic flame presence detection | ~300 B/s |
| Flicker + low thermoacoustic (100 Hz) | 200 Hz | 500 Hz – 1 kHz | Stability monitoring | ~1.5 KB/s |
| **Full combustion dynamics (500 Hz)** | **1 kHz** | **2–5 kHz** | **RECOMMENDED for furnace monitoring** | **~7.5 KB/s** |
| Research-grade analysis (1 kHz) | 2 kHz | 10 kHz | Detailed combustion analysis | ~15 KB/s |

### 2.2 Practical Recommendation for ESP32-S3

**Primary recommendation: 2 kHz continuous sampling**

This rate provides:

- Nyquist coverage to 1 kHz (capturing all practical combustion dynamics)
- Manageable data volume (~60 MB/hour per channel at 12-bit)
- Adequate margin for FFT frequency resolution (1 Hz bins with 2-second windows)
- Comfortable headroom for ESP32-S3 DMA ADC operation

**Alternative: Burst sampling at 10 kHz**

If storage is constrained, consider burst sampling: capture 1-second buffers at 10 kHz every 30–60 seconds. This provides research-grade snapshots while minimizing data volume.

---

## 3. Analysis Techniques

### 3.1 Fast Fourier Transform (FFT)

FFT is the foundational tool for combustion frequency analysis. It converts time-domain signals into frequency-domain power spectra, revealing dominant oscillation frequencies.

**Implementation parameters:**

- **Window size:** 1024–4096 samples (0.5–2 seconds at 2 kHz)
- **Overlap:** 50% for continuous monitoring
- **Window function:** Hanning or Hamming to reduce spectral leakage
- **Frequency resolution:** Sample rate ÷ window size (e.g., 2000 ÷ 2048 ≈ 1 Hz)

**What to look for:** Sharp peaks indicate coherent oscillations. During stable combustion, expect a broad peak around 10 Hz (flicker) and possibly equipment-specific peaks. Developing instability shows narrowing peaks with growing harmonics.

### 3.2 Flame Stability Indices

Beyond simple FFT, several derived metrics are used in combustion research:

1. **RMS amplitude:** Root-mean-square of signal fluctuations. Sudden increases indicate developing instability.

2. **Spectral centroid:** "Center of mass" of frequency spectrum. Shifts indicate changing combustion dynamics.

3. **Spectral spread:** Bandwidth around centroid. Narrowing spread with rising amplitude = instability precursor.

4. **Peak-to-peak ratio:** Ratio of dominant peak to second harmonic. Changes indicate waveform distortion.

5. **Temporal irreversibility (T3):** Measures asymmetry of oscillation waveform. Sawtooth patterns (high T3) indicate thermoacoustic coupling.

### 3.3 Instability Precursor Detection

Modern combustion research has developed methods to predict instability *before* it occurs—typically 100–500 ms in advance. These are active research areas with industrial applications:

- **Permutation entropy:** Quantifies signal complexity; drops as instability approaches
- **Recurrence quantification analysis:** Detects repeating patterns emerging from noise
- **Hurst exponent:** Long-range correlation measure; increases before instability
- **Machine learning classifiers:** Neural networks trained on pressure/heat release data

**Practical note:** These advanced techniques require baseline data from both stable and unstable operation. Start with FFT and simple statistics; add sophisticated precursor detection as you accumulate training data.

---

## 4. Interpreting Your Data

The research document should help answer: "I'm seeing X pattern in my flame sensor data at Y frequency—is this meaningful or noise?"

### 4.1 Pattern Interpretation Guide

| Observation | Likely Cause | Action |
|-------------|--------------|--------|
| Stable ~10 Hz peak with low harmonics | Normal flame flicker | Good combustion; use as baseline |
| Sharp peaks with integer harmonics (10, 20, 30 Hz...) | Developing thermoacoustic resonance | Monitor closely; may need operational adjustment |
| Broadband increase across all frequencies | Increased turbulence / combustion noise | Check air-fuel ratio; may indicate lean operation |
| Loss of 10 Hz peak; erratic signal | Flame instability / lift-off | Potential danger; verify flame status immediately |
| Very low frequency drift (<1 Hz) | Atmospheric pressure changes | Normal; correlate with barometer data |
| Sudden RMS spike with narrowing spectrum | Instability precursor | Warning sign; take corrective action |

---

## 5. Key Research Sources

This document synthesizes findings from peer-reviewed combustion research and industrial studies:

1. **Babcock & Wilcox (2017):** "Thermoacoustic Vibrations in Industrial Furnaces and Boilers" — Field study of industrial boiler rumble with 10 Hz dominant oscillation

2. **Scientific Reports (2024):** "Stability study of flame structure using photodiodes in surface flame burners" — 10 kHz sampling, FFT analysis, 9–10 Hz peaks

3. **Nature Scientific Reports (2019):** "Frequency and Phase Characteristics of Candle Flame Oscillation" — ~10 Hz flicker frequency across flame types

4. **Combustion and Flame literature:** Multiple studies on thermoacoustic oscillations (50–1000 Hz range)

5. **AIP Chaos (2021):** "Early detection of thermoacoustic instabilities" — Machine learning precursor detection

6. **Applied Optics (2008):** "Photodiode-based sensor for flame sensing and combustion-process monitoring" — Silicon photodiode flame sensing

---

## 6. Conclusions

The questions about flame dynamics that "can't be answered" actually have substantial research literature behind them. For your propane-fired glass furnace:

- **Primary frequencies of interest:** 1–500 Hz, with emphasis on 8–12 Hz (flicker) and your furnace-specific acoustic modes
- **Sample at 2 kHz minimum** for continuous monitoring; 10 kHz for detailed analysis
- **FFT is your primary analysis tool**; look for stable ~10 Hz flicker as baseline
- **Sharp harmonics indicate developing resonance**; broadband noise indicates combustion quality changes
- **Advanced precursor detection is achievable** once you have baseline data from both stable and unstable conditions

Your ESP32-S3's 2 MSPS capability is massive overkill for combustion dynamics—but having that headroom means you won't miss anything. The real constraint is storage and analysis bandwidth, not sampling capability.

**Next steps:** Establish baseline FFT spectra during known-good combustion, then systematically characterize your furnace's frequency response under varying conditions (load, atmospheric pressure, fuel quality). This empirical mapping will be more valuable than any theoretical prediction.

---

*Created: November 2025*  
*Project: Lyon's Pyre Glasswerks Furnace Monitoring*  
*Purpose: Instrumentation design reference for combustion frequency analysis*
