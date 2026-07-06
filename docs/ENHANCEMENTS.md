# AQOS Enhancement Backlog

> AI Quant Operating System (AQOS)
>
> This document tracks enhancements intentionally deferred during development.
>
> These are **not bugs**. They are planned improvements that will be implemented in future sprints when the supporting infrastructure is available.

---

# Status

Current Version

```
v0.5.0-dev
```

---

# Guiding Principle

During early sprints we build **clean, modular foundations**.

Production-grade AI functionality is intentionally deferred until the required infrastructure exists.

Every enhancement listed here has been consciously postponed.

---

# Sprint 004 Deferred Enhancements

## Strategy Engine

### Pattern Detector

Future improvements

- Multi-candle pattern recognition
- Pattern confidence scoring
- Pattern clustering
- Volume confirmation
- Pattern history tracking

---

### Market Regime

Future improvements

- Hidden Markov Models
- Bayesian regime detection
- Volatility-based regimes
- AI regime classification
- Multi-timeframe regime analysis

---

### Support & Resistance

Future improvements

- Dynamic support/resistance
- Volume profile integration
- Order block detection
- Fair Value Gap detection
- Institutional liquidity zones

---

### Liquidity

Future improvements

- Liquidity sweep detection
- Stop hunt identification
- Smart Money Concepts
- Order flow analysis
- Depth-of-market integration

---

### Trend Structure

Future improvements

- Multi-timeframe trend alignment
- Swing strength analysis
- Break of Structure (BoS)
- Change of Character (ChoCH)
- Elliott Wave integration

---

### Signal Engine

Future improvements

- Weighted ensemble voting
- Confidence scoring
- AI signal ranking
- Multi-model consensus
- Signal explainability

---

### Entry / Exit Engine

Future improvements

- Dynamic entry timing
- Confirmation filters
- Volatility filters
- Time-based exits
- Event-driven exits

---

### Stop Loss / Take Profit

Future improvements

- ATR-based levels
- Volatility-adjusted exits
- Adaptive Risk/Reward
- Trailing stop logic
- Partial profit taking

---

# Sprint 005 Deferred Enhancements

## Models

### Base Model

Future improvements

- Native PyTorch support
- Native TensorFlow support
- ONNX model support
- GPU awareness
- Distributed training hooks

---

### Dataset

Future improvements

- Time-series dataset builder
- Sliding window generation
- Sequence dataset creation
- Automatic train/validation/test split
- Dataset versioning
- Dataset caching

---

### Predictor

Future improvements

- Batch inference
- Streaming inference
- Online prediction
- Multi-model prediction
- Async prediction pipeline

---

### Encoder

Future improvements

- Categorical encoding
- Feature normalization
- Standardization
- Missing-value encoding
- Embedding generation

---

### Transformer

Future improvements

- Feature scaling
- PCA
- Feature selection
- Dimensionality reduction
- Learned feature transformations

---

### Similarity Engine

Future improvements

- Cosine similarity
- Euclidean distance
- Dynamic Time Warping (DTW)
- FAISS integration
- Approximate nearest neighbor search
- Pattern similarity retrieval

---

### Uncertainty Engine

Future improvements

- Bayesian uncertainty
- Monte Carlo Dropout
- Ensemble uncertainty
- Confidence calibration
- Prediction intervals

---

### World Model

Future improvements

- Latent market representation
- Market state transitions
- Temporal memory
- Transformer-based world model
- Reinforcement Learning environment model
- Probabilistic market simulation

---

# Global Enhancements

Future system-wide improvements

## Performance

- Parallel pipelines
- GPU acceleration
- Async processing
- Distributed execution
- Memory optimization

---

## AI

- Transformer models
- Reinforcement Learning
- Foundation Models
- Agentic AI
- Retrieval-Augmented Generation (RAG)

---

## Quantitative Research

- Feature Store
- Experiment Tracking
- Hyperparameter Optimization
- AutoML
- Portfolio Optimization

---

## Infrastructure

- Docker deployment
- Kubernetes support
- Cloud-native architecture
- CI/CD automation
- Model registry
- Artifact versioning

---

# Enhancement Rules

1. Never implement an enhancement unless its prerequisite modules exist.
2. Keep the foundation simple before adding intelligence.
3. Large enhancements should be implemented in dedicated future sprints.
4. Completed enhancements should be removed from this document and recorded in the CHANGELOG.

---

# Notes

This document serves as the long-term enhancement backlog for AQOS.

It ensures that promising ideas are not forgotten while keeping the implementation focused, modular, and aligned with the project's roadmap.