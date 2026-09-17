

def test_prediction_subsumes_its_embedded_rating_and_injury_inputs():
    from v2.runtime.subsumption import capability_subsumes
    assert capability_subsumes("game_prediction", "team_ratings")
    assert capability_subsumes("game_prediction", "injuries")
    assert capability_subsumes("game_prediction", "injury_impact")
