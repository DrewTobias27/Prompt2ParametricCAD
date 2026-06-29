from prompt2cad.feature_tree_export import model_data_to_feature_tree


def test_model_data_to_feature_tree_exports_debug_tree():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 8,
                "width": 80,
                "height": 50,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 10,
            },
        ]
    }

    feature_tree = model_data_to_feature_tree(model_data)

    assert feature_tree["build_order"] == ["base", "cut_2"]
    assert feature_tree["features"][1]["canonical_target"] == "base.face.f001"
    assert feature_tree["features"][1]["sketch"]["entities"][1]["id"] == "c001"
    assert feature_tree["registry"]["aliases"]["base.top"] == "base.face.f001"
