from sts2_tas.torch_rl import PPO_EXTENSION_PLAN, ppo_is_available


def test_ppo_extension_plan_stays_planned_for_v1() -> None:
    assert PPO_EXTENSION_PLAN.algorithm == "PPO"
    assert PPO_EXTENSION_PLAN.status == "planned"
    assert "stable simulator environment" in PPO_EXTENSION_PLAN.prerequisites
    assert "no PPO optimizer in v1" in PPO_EXTENSION_PLAN.explicit_exclusions
    assert ppo_is_available() is False
