import vowpalwabbit as vw
import pickle
import pandas as pd
import random
import os

MODEL_PATH = "models/dropout_model.pkl"
RL_MODEL_PATH = "models/rl_agent.vw"

ACTIONS = {
    1: "morning_reminder",
    2: "evening_reminder",
    3: "motivational_message",
    4: "escalate_to_doctor",
    5: "do_nothing"
}

ACTION_MESSAGES = {
    1: "Good morning! Did you take your medicine today? Reply YES or NO. 💊",
    2: "Good evening! Don't forget your medicine tonight. Reply YES or NO. 🌙",
    3: "You're doing great! Every dose counts. Keep going 💪 Reply YES or NO.",
    4: "DOCTOR ALERT: Patient has missed multiple doses. Please follow up.",
    5: None
}


def build_vw_example(context: dict, action: int = None, reward: float = None) -> str:
    """Build a VW-formatted contextual bandit example."""
    streak = context.get("reply_streak", 0)
    skip_rate = context.get("skip_rate_so_far", 0.0)
    risk = context.get("risk_score", 0.5)
    hour = context.get("hour_of_day", 9)
    day_of_week = context.get("day_of_week", 0)
    is_weekend = context.get("is_weekend", 0)

    features = (
        f"streak:{streak} "
        f"skip:{skip_rate:.2f} "
        f"risk:{risk:.2f} "
        f"hour:{hour} "
        f"dow:{day_of_week} "
        f"weekend:{is_weekend}"
    )

    if action is not None and reward is not None:
        # Training format: action:cost:probability | features
        cost = -reward  # VW minimizes cost, we maximize reward
        return f"{action}:{cost:.2f}:0.2 | {features}"
    else:
        # Prediction format
        return f"| {features}"


def get_reward(action: int, patient_replied: bool, was_high_risk: bool) -> float:
    if action == 5:  # do_nothing
        return 0.0

    if action == 4:  # escalate_to_doctor
        if was_high_risk and patient_replied:
            return 2.0   # escalation worked on high-risk patient
        elif was_high_risk and not patient_replied:
            return -0.3  # high-risk but no response
        else:
            return -1.0  # unnecessary escalation on low/medium risk

    if patient_replied:
        return 1.0   # any reminder got a reply
    else:
        return -0.5  # reminder ignored

class HealOAgent:
    def __init__(self, epsilon=0.1):
        self.epsilon = epsilon
        self.vw_model = vw.Workspace(
            f"--cb 5 --epsilon {epsilon} --quiet"
        )
        self.action_counts = {i: 0 for i in range(1, 6)}
        self.reward_history = []

    def select_action(self, context: dict) -> tuple:
        """Select action using epsilon-greedy contextual bandit."""
        example = build_vw_example(context)
        action = self.vw_model.predict(example)

        # Clamp to valid range
        if not isinstance(action, int) or action < 1 or action > 5:
            action = random.randint(1, 5)

        self.action_counts[action] += 1
        return action, ACTION_MESSAGES[action]

    def update_policy(self, context: dict, action: int, reward: float):
        """Update policy after observing reward."""
        example = build_vw_example(context, action, reward)
        self.vw_model.learn(example)
        self.reward_history.append(reward)

    def save(self, path: str):
        self.vw_model.save(path)
        print(f"RL agent saved to {path}")

    def get_stats(self) -> dict:
        return {
            "total_decisions": sum(self.action_counts.values()),
            "action_distribution": {
                ACTIONS[k]: v for k, v in self.action_counts.items()
            },
            "avg_reward": (
                sum(self.reward_history) / len(self.reward_history)
                if self.reward_history else 0.0
            )
        }


def load_dropout_model():
    with open(MODEL_PATH, "rb") as f:
        data = pickle.load(f)
    return data["model"], data["label_encoder"]


def get_risk_score(model, le, patient_features: dict) -> tuple:
    """Get numeric risk score from XGBoost model."""
    feature_order = [
        "reply_streak", "skip_rate_so_far", "weekend_skip_rate",
        "avg_reply_latency_seconds", "is_weekend",
        "messages_sent", "responses_received", "replied_today"
    ]
    row = [[patient_features.get(f, 0) for f in feature_order]]
    proba = model.predict_proba(row)[0]
    pred_class = model.predict(row)[0]
    label = le.inverse_transform([pred_class])[0]

    # Map to numeric: Low=0.2, Medium=0.5, High=0.9
    risk_map = {"Low": 0.2, "Medium": 0.5, "High": 0.9}
    return risk_map.get(label, 0.5), label


def simulate_rl_training(n_episodes=500):
    """Simulate RL agent learning over synthetic patient interactions."""
    print("Loading dropout model...")
    dropout_model, le = load_dropout_model()

    print("Initializing RL agent...")
    agent = HealOAgent(epsilon=0.1)

    print(f"Running {n_episodes} simulation episodes...")

    results = []

    for episode in range(n_episodes):
        # Simulate a patient day context
        patient_type = random.choices(
            ["adherent", "erratic", "early_dropout", "recoverer"],
            weights=[0.30, 0.25, 0.30, 0.15]
        )[0]

        streak = random.randint(0, 14) if patient_type == "adherent" else random.randint(0, 5)
        skip_rate = random.uniform(0.0, 0.2) if patient_type == "adherent" else random.uniform(0.2, 0.8)
        hour = random.randint(7, 21)
        day_of_week = random.randint(0, 6)
        is_weekend = 1 if day_of_week >= 5 else 0
        latency = random.randint(300, 7200)

        patient_features = {
            "reply_streak": streak,
            "skip_rate_so_far": skip_rate,
            "weekend_skip_rate": skip_rate * 1.2,
            "avg_reply_latency_seconds": latency,
            "is_weekend": is_weekend,
            "messages_sent": random.randint(1, 30),
            "responses_received": max(0, random.randint(0, 28)),
            "replied_today": 0
        }

        risk_score, risk_label = get_risk_score(dropout_model, le, patient_features)

        context = {
            "reply_streak": streak,
            "skip_rate_so_far": skip_rate,
            "risk_score": risk_score,
            "hour_of_day": hour,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend
        }

        # Agent selects action
        action, message = agent.select_action(context)

        # Simulate patient response based on type + action
        if patient_type == "adherent":
            reply_prob = 0.85
        elif patient_type == "erratic":
            reply_prob = 0.5 if is_weekend else 0.7
        elif patient_type == "early_dropout":
            reply_prob = 0.2
        else:
            reply_prob = 0.55

        # Motivational messages get a small boost
        if action == 3:
            reply_prob = min(reply_prob + 0.1, 1.0)
        # Evening reminders slightly better than morning
        if action == 2:
            reply_prob = min(reply_prob + 0.05, 1.0)

        patient_replied = random.random() < reply_prob
        was_high_risk = risk_label == "High"

        reward = get_reward(action, patient_replied, was_high_risk)
        agent.update_policy(context, action, reward)

        results.append({
            "episode": episode,
            "patient_type": patient_type,
            "risk_label": risk_label,
            "action": ACTIONS[action],
            "patient_replied": patient_replied,
            "reward": reward
        })

        if (episode + 1) % 100 == 0:
            stats = agent.get_stats()
            print(f"Episode {episode+1}: avg_reward={stats['avg_reward']:.3f}")

    os.makedirs("models", exist_ok=True)
    agent.save(RL_MODEL_PATH)

    results_df = pd.DataFrame(results)
    results_df.to_csv("models/rl_training_results.csv", index=False)

    print("\n" + "=" * 50)
    print("RL TRAINING COMPLETE")
    print("=" * 50)

    stats = agent.get_stats()
    print(f"Total decisions: {stats['total_decisions']}")
    print(f"Average reward:  {stats['avg_reward']:.3f}")
    print("\nAction distribution:")
    for action_name, count in stats["action_distribution"].items():
        pct = count / stats["total_decisions"] * 100
        print(f"  {action_name:<25} {count:>5} ({pct:.1f}%)")

    print("\nReward by patient type:")
    for ptype in ["adherent", "erratic", "early_dropout", "recoverer"]:
        subset = results_df[results_df["patient_type"] == ptype]
        print(f"  {ptype:<20} avg_reward = {subset['reward'].mean():.3f}")

    print(f"\nSaved RL agent  → models/rl_agent.vw")
    print(f"Saved results   → models/rl_training_results.csv")

    return agent, results_df


if __name__ == "__main__":
    simulate_rl_training(n_episodes=500)