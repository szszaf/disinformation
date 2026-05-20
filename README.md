# Disinformation & Online Debate Escalation Poster

This repository contains a project poster: [disinformation_poster.pdf](./disinformation_poster.pdf).

## Overview

The poster presents a study on how online discussions escalate in Reddit communities. The project introduces a custom **discussion temperature** metric to identify users and comments that intensify or de-escalate debates.

The analysis focuses on selected subreddits related to conspiracy theories and polarizing topics, compared with a neutral control community.

## Dataset

Data was collected using the Reddit API and includes:

- 5 subreddits: `flatearth`, `aliens`, `chemtrails`, `animals`, `news`
- 2,214 posts
- 168k comments
- 61k users

## Main Methods

The project combines several signals to estimate discussion temperature:

- toxicity detection using `unitary/toxic-bert`
- reply speed and engagement
- voting controversy
- context from previous comments
- clustering of user behavior with K-Means
- qualitative comment categorization using an LLM-as-a-judge approach

## Key Findings

The analysis identified three main user roles:

- **Regular users**
- **Mediators**
- **Provocateurs**

Conspiracy-related communities showed a higher share of provocative users than hobby-oriented communities. The study also found that hotter discussions tend to use fewer external sources and contain shorter comments.

## Authors

Marcel Masiukiewicz, Bartłomiej Ruszaj, Szymon Szafraniec, Marcin Tkocz

Project prepared for the **Digital Media Analysis** course in the Artificial Intelligence program, 2026.
