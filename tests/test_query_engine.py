import pytest

from modules import query_engine


def test_aggregate_plan_and_execute(sample_df):
    result = query_engine.answer_question("What is the total revenue?", sample_df)
    assert result.plan.operation == "aggregate"
    assert result.plan.metric_col == "revenue"
    assert result.scalar == pytest.approx(sample_df["revenue"].sum())


def test_groupby_plan(sample_df):
    result = query_engine.answer_question("revenue by region", sample_df)
    assert result.plan.operation == "groupby"
    assert set(result.data.columns) == {"region", "revenue"}
    assert len(result.data) == sample_df["region"].nunique()


def test_trend_plan(sample_df):
    result = query_engine.answer_question("monthly revenue trend", sample_df)
    assert result.plan.operation == "trend"
    assert result.plan.freq == "ME"
    assert not result.data.empty


def test_correlation_plan(sample_df):
    result = query_engine.answer_question(
        "correlation between quantity and profit", sample_df
    )
    assert result.plan.operation == "correlation"
    assert -1.0 <= result.scalar <= 1.0


def test_unrecognized_question_raises(sample_df):
    with pytest.raises(query_engine.QueryError):
        query_engine.answer_question("what is the meaning of life", sample_df)


def test_rejects_nonexistent_column_at_execution(sample_df):
    plan = query_engine.QueryPlan(operation="aggregate", metric_col="not_a_real_column")
    with pytest.raises(query_engine.QueryError):
        query_engine.execute_plan(plan, sample_df)


def test_pronoun_resolution(sample_df):
    result = query_engine.answer_question("what about its monthly trend?", sample_df,
                                            last_metric_col="profit")
    assert result.plan.metric_col == "profit"
    assert result.plan.resolved_note
