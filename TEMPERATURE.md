# Reddit Activity Temperature Metric Specification

This document outlines the logic, mathematics, and implementation details for calculating the **"Temperature"** of Reddit threads. This metric is designed to detect engagement intensity, emotional heat, and controversial friction over time.

## 1. Input Data Schema

The algorithm consumes a CSV dataset containing Reddit activities (both Posts and Comments).

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `activity_id` | String | Unique identifier for the activity. |
| `activity_type` | String | `post` or `comment`. |
| `subreddit` | String | for now always `conspiracy`. |
| `timestamp` | Datetime | Creation time of the activity (UTC). |
| `author` | String | Username of the creator. |
| `parent_id` | String | ID of the parent activity (post or comment being replied to). |
| `parent_type` | String | `post` or `comment`. |
| `content` | String | The raw text body of the activity. |
| `score` | Int | Net score (Upvotes - Downvotes). |
| `upvotes` | Int | Total upvotes. |
| `downvotes` | Int | Total downvotes (available for posts). |
| `upvote_ratio` | Float | Ratio of upvotes to total votes (0.0 to 1.0; posts only). |
| `num_comments` | Int | Total comments on the thread (at time of capture). |
| `edited` | Boolean | `True` if the activity was edited. |

---

## 2. Methodology Overview

Temperature is **not** a static value. It is calculated in **Time Windows** (TimeSeries).

1.  **Grouping:** Data must be grouped by the original Thread (Root Post).
2.  **Windowing:** Activities within a thread are bucketed into discrete time intervals - let's assume 1 hour window.
3.  **Calculation:** A single Temperature score ($T$) is calculated for each window based on the activities that occurred *within* that window.

---

## 3. The Temperature Formula

For a given time window $w$, the Raw Energy ($E_w$) is the product of four components:

$$E_w = V_w \times U_w \times H_w \times F_w$$

### A. Velocity ($V_w$) — *Activity Density*

**Logic:** Measures the sheer volume of conversation.
**Why:** A flame war requires participants. However, we use a logarithmic scale because the difference between 0 and 10 comments is massive, but the difference between 1000 and 1010 is negligible. 

$$V_w = \ln(1 + N_{comments})$$

* $N_{comments}$: The count of **new comments** posted within this specific window. $N_{comments}$ is number of comment type activities that timestamp is in range of time window
* *Note:* Posts are excluded from this count; they are handled in Friction.

### B. Urgency ($U_w$) — *Reply Speed*

**Logic:** Measures how "obsessively" people are refreshing the page to argue.
**Why:** In heated arguments, replies happen in seconds. In casual discussions, they happen in hours.

$$U_w = \frac{1}{\ln(e + \bar{t}_{lag})}$$

* $\bar{t}_{lag}$: The average time difference (in seconds) between a comment in this window and its specific `parent_id`.
* $e$: Euler's number ($\approx 2.718$). Added to ensure the denominator is always $> 1$, preventing division by zero.
* *Handling Missing Data:* If a window contains only the initial Post (no comments), $U_w$ should default to a neutral value (e.g., 0.5).

### C. Emotional Heat ($H_w$) — *Linguistic Intensity*

**Logic:** The core NLP layer. It combines AI-detected toxicity with specific linguistic patterns associated with conflict.
**Why:** A thread can be fast (Velocity) but polite (Q&A). High heat requires negative emotion or tribalism.

$$H_w = (1 + \bar{S}_{toxic}) \times (1 + \Sigma_{triggers})$$

#### Part 1: Toxicity ($\bar{S}_{toxic}$)
* **Source:** `unitary/toxic-bert` model.
* **Calculation:** The average probability score (0.0 to 1.0) of the all toxicities returned by model, for all text in the window. model returns a few kinds of toxicity like toxicity, obscene, insult, identity attack etc.

#### Part 2: Social Triggers ($\Sigma_{triggers}$)
This detects the density of "fighting words." It is a weighted sum of three densities:

$$\Sigma_{triggers} = (0.2 \cdot D_{you}) + (0.15 \cdot D_{them}) + (0.1 \cdot D_{abs})$$

Where $D$ is the **Density** of the pattern:
$$D_{pattern} = \frac{\text{Count of Pattern Matches in Window}}{\text{Total Word Count in Window}} \times 100$$

**Trigger Patterns:**
1.  **Direct Address ($D_{you}$):** Confrontational language.
    * *Regex:* `\b(you|your|yours|u|ur)\b`
2.  **"Us vs. Them" ($D_{them}$):** Othering/Tribalism.
    * *Regex:* `\b(they|them|their|theirs|those people)\b`
    * *Note:* Often contrasted with "we/us", but high usage of "they" is the stronger conflict signal.
3.  **Absolutism ($D_{abs}$):** Dogmatic language (lack of nuance).
    * *Regex:* `\b(always|never|everyone|nobody|totally|absolutely|fact|proven)\b`

### D. Friction ($F_w$) — *The Ignition Multiplier*

**Logic:** Measures how controversial the topic is based on community voting behavior.
**Why:** A post with 50% upvotes and 50% downvotes is the definition of "controversial."
**Constraint:** This applies **only** to the window containing the creation of the Post. For all other windows, $F_w = 1$.

$$F_w = 1 + \left( 1 - \left| 2 \times (R_{up} - 0.5) \right| \right)$$

* $R_{up}$: The value from the `upvote_ratio` column (0.0 to 1.0).
* **Result:**
    * If Ratio is 0.5 (50%): Friction = 2.0 (Max Heat).
    * If Ratio is 1.0 (100%) or 0.0 (0%): Friction = 1.0 (No added heat).

---

## 4. Normalization (Final Score)

The Raw Energy $E_w$ is unbounded. To visualize it effectively, we map it to a **0-10 Scale**.

**Recommended Method: Sigmoid Scaling**
This handles outliers gracefully (a massive viral thread won't flatten the rest of the data).

$$T_{final} = \frac{10}{1 + e^{-k \cdot (E_w - M)}}$$

* **$M$ (Midpoint):** The energy level considered "active." *Suggested Start: 10.0*
* **$k$ (Steepness):** Sensitivity of the curve. *Suggested Start: 0.2*

---

## 5. Implementation Summary (Pseudocode)

```python
# For every Time Window in every Thread:

1. FILTER activities belonging to this window.

2. IF window is empty:
      Temperature = 0
      RETURN

3. CALCULATE Velocity:
      count = number of comments
      V = log(1 + count)

4. CALCULATE Urgency:
      lags = [timestamp - parent_timestamp for comment in window]
      avg_lag = mean(lags)
      U = 1 / log(2.718 + avg_lag)

5. CALCULATE Heat:
      # NLP Processing
      toxicity_score = mean(BERT_scores)
      
      # Regex Counting
      text_blob = join(all_content)
      D_you = (count("you", "your"...) / total_words) * 100
      D_them = (count("they", "them"...) / total_words) * 100
      D_abs = (count("always", "never"...) / total_words) * 100
      
      triggers = (0.2 * D_you) + (0.15 * D_them) + (0.1 * D_abs)
      H = (1 + toxicity_score) * (1 + triggers)

6. CALCULATE Friction:
      IF window contains Post:
          ratio = post.upvote_ratio
          F = 1 + (1 - abs(2 * (ratio - 0.5)))
      ELSE:
          F = 1

7. COMPUTE Raw Energy:
      E = V * U * H * F

8. NORMALIZE:
      Temperature = 10 / (1 + exp(-0.2 * (E - 10)))

9. CREATE interactive plot with plotly for convinient exploration of results  