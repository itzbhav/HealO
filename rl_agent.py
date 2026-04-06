import pandas as pd
import numpy as np
import pickle
import json
import random
from datetime import datetime

# ── RL Contextual Bandit (Vowpal Wabbit) ──────────────────────────────────
try:
    import vowpalwabbit as vw
    VW_AVAILABLE = True
except ImportError:
    VW_AVAILABLE = False
    print("⚠️  vowpalwabbit not installed. Run: pip install vowpalwabbit")
    print("   Falling back to epsilon-greedy bandit simulation.\n")

# ── Actions ───────────────────────────────────────────────────────────────
ACTIONS = {
    1: "morning_reminder",
    2: "evening_reminder",
    3: "motivational_message",
    4: "escalate_to_doctor",
    5: "do_nothing"
}

ACTION_MESSAGES = {
    1: "Good morning! 🌅 Don't forget your medication today. Reply YES once taken 💊",
    2: "Good evening! 🌙 Have you taken your medication today? Reply YES or NO 💊",
    3: "You're doing amazing! 💪 Every dose brings you closer to better health. Reply YES if taken!",
    4: "⚠️ DOCTOR ALERT: Patient has not responded for several days. Escalating to care team.",
    5: None  # do nothing
}

# ── Epsilon-Greedy Fallback Bandit ────────────────────────────────────────
class EpsilonGreedyBandit:
    def __init__(self, n_actions=5, epsilon=0.1):
        self.n_actions = n_actions
        self.epsilon = epsilon
        self.counts  = np.zeros(n_actions)
        self.values  = np.zeros(n_actions)

    def select_action(self, context: dict) -> int:
        # Risk-based override
        if context.get("risk_score", 0) > 0.7 and context.get("days_since_reply", 0) >= 3:
            return 4  # escalate
        if random.random() < self.epsilon:
            return random.randint(1, self.n_actions)
        return int(np.argmax(self.values)) + 1

    def update(self, action: int, reward: float):
        idx = action - 1
        self.counts[idx] += 1
        n = self.counts[idx]
        self.values[idx] += (reward - self.values[idx]) / n

# ── VW Bandit ─────────────────────────────────────────────────────────────
class VWBandit:
    def __init__(self, n_actions=5, epsilon=0.1):
        self.model = vw.Workspace(f"--cb {n_actions} --epsilon {epsilon} --quiet")
        self.n_actions = n_actions

    def _make_example(self, context: dict, action: int = None, reward: float = None) -> str:
        features = (
            f"streak:{context.get('streak', 0)} "
            f"skip:{context.get('weekend_skip_rate', 0):.2f} "
            f"risk:{context.get('risk_score', 0):.2f} "
            f"latency:{context.get('avg_latency_min', 0):.0f} "
            f"days_silent:{context.get('days_since_reply', 0)} "
            f"hour:{context.get('hour', 9)} "
            f"weekday:{context.get('weekday', 0)}"
        )
        if action and reward is not None:
            cost = -reward  # VW minimizes cost
            return f"{action}:{cost:.2f}:0.2 | {features}"
        return f"| {features}"

    def select_action(self, context: dict) -> int:
        if context.get("risk_score", 0) > 0.7 and context.get("days_since_reply", 0) >= 3:
            return 4
        example = self._make_example(context)
        action = self.model.predict(example)
        return max(1, min(self.n_actions, int(action)))

    def update(self, context: dict, action: int, reward: float):
        example = self._make_example(context, action, reward)
        self.model.learn(example)

# ── Reward Function ───────────────────────────────────────────────────────
def compute_reward(action: int, patient_responded: bool,
                   was_high_risk: bool, patient_blocked: bool) -> float:
    if patient_blocked:
        return -1.0
    if action == 4 and was_high_risk and patient_responded:
        return 2.0   # high-risk patient re-engaged after escalation
    if patient_responded:
        return 1.0   # dose confirmed
    if action == 5:
        return 0.0   # do nothing — neutral
    return -0.5      # sent message but no response

# ── Predict dropout risk using saved model ────────────────────────────────
def predict_risk(patient_features: dict) -> float:
    try:
        with open("dropout_model.pkl", "rb") as f:
            model = pickle.load(f)
        cols = ["reply_rate", "streak", "weekend_skip_rate",
                "avg_latency_min", "days_since_reply", "med_taken_rate",
                "latency_drift", "recent_reply_rate", "disease_enc"]
        X = np.array([[patient_features.get(c, 0) for c in cols]])
        prob = model.predict_proba(X)[0][1]
        return float(prob)
    except Exception as e:
        return 0.5  # default medium risk if model unavailable

# ── Full Simulation ───────────────────────────────────────────────────────
def run_rl_simulation():
    print("\n🤖 Initialising RL Contextual Bandit...")

    if VW_AVAILABLE:
        bandit = VWBandit(n_actions=5, epsilon=0.1)
        print("   Using: Vowpal Wabbit Contextual Bandit ✅")
    else:
        bandit = EpsilonGreedyBandit(n_actions=5, epsilon=0.1)
        print("   Using: Epsilon-Greedy Fallback Bandit ✅")

    df = pd.read_csv("patient_features.csv")
    print(f"   Patients to run interventions for: {len(df)}\n")

    total_rewards = []
    action_counts = {a: 0 for a in ACTIONS}
    results = []

    print("🔄 Simulating interventions across all patients...\n")

    for _, row in df.iterrows():
        context = {
            "streak":            int(row["streak"]),
            "weekend_skip_rate": float(row["weekend_skip_rate"]),
            "avg_latency_min":   float(row["avg_latency_min"]),
            "days_since_reply":  int(row["days_since_reply"]),
            "risk_score":        float(row["recent_reply_rate"] < 0.4),
            "hour":              random.choice([8, 9, 18, 19, 20]),
            "weekday":           random.randint(0, 6),
            "med_taken_rate":    float(row["med_taken_rate"]),
        }

        # Predict risk from XGBoost model
        context["risk_score"] = predict_risk({**dict(row), "disease_enc": 0})

        # Select action
        action = bandit.select_action(context)
        action_counts[action] += 1

        # Simulate patient response based on their profile
        is_dropout = row["dropout_label"] == 1
        base_response_prob = row["reply_rate"]
        if action == 1 and row["avg_latency_min"] < 120:
            base_response_prob += 0.1   # morning works for fast responders
        elif action == 2 and row["avg_latency_min"] >= 120:
            base_response_prob += 0.1   # evening works for slow responders
        elif action == 3 and is_dropout:
            base_response_prob += 0.15  # motivational helps dropouts
        elif action == 4 and is_dropout:
            base_response_prob += 0.20  # escalation helps high-risk

        patient_responded = random.random() < min(base_response_prob, 0.99)
        patient_blocked   = random.random() < 0.01  # 1% block rate

        reward = compute_reward(action, patient_responded, is_dropout, patient_blocked)
        total_rewards.append(reward)

        # Update bandit
        if VW_AVAILABLE:
            bandit.update(context, action, reward)
        else:
            bandit.update(action, reward)

        results.append({
            "patient_id":   int(row["patient_id"]),
            "risk_score":   round(context["risk_score"], 3),
            "action":       ACTIONS[action],
            "responded":    patient_responded,
            "reward":       reward,
            "is_dropout":   is_dropout,
        })

    # ── Summary ───────────────────────────────────────────────────────────
    results_df = pd.DataFrame(results)
    results_df.to_csv("rl_results.csv", index=False)

    print("📊 RL Simulation Results:")
    print(f"   Total patients:     {len(results_df)}")
    print(f"   Avg reward:         {np.mean(total_rewards):.3f}")
    print(f"   Response rate:      {results_df['responded'].mean()*100:.1f}%")
    print(f"   High-risk detected: {(results_df['risk_score'] > 0.5).sum()}")
    print(f"\n🎯 Action Distribution:")
    for action_id, action_name in ACTIONS.items():
        count = action_counts[action_id]
        pct   = count / len(results_df) * 100
        bar   = "█" * int(pct / 2)
        print(f"   {action_name:<25} {count:>4} ({pct:4.1f}%)  {bar}")

    print(f"\n📁 Saved: rl_results.csv")
    print(f"\n✅ Done! Full pipeline complete:")
    print(f"   simulate_journeys.py → build_features.py → train_model.py → rl_agent.py")
    print(f"\n🚀 Next step: python dashboard.py  (Streamlit doctor dashboard)")

if __name__ == "__main__":
    print("🚀 HealO — RL Contextual Bandit Intervention Agent")
    print("=" * 52)
    run_rl_simulation()
