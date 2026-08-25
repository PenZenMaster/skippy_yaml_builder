from main import YAMLForm


def test_every_input_field_appears_in_exactly_one_tab_field_list(qapp):
    # A field left out of all three would still work for save/load (that
    # loop iterates self.inputs directly, not the tab layouts), but would
    # be invisible/unreachable in the UI -- see _build_tabs's own doc
    # comment for why this must hold.
    tab_fields = (
        YAMLForm.CLIENT_INFO_FIELDS + YAMLForm.CONTENT_FIELDS + YAMLForm.YACSS_BUILD_FIELDS
    )

    form = YAMLForm()

    assert sorted(tab_fields) == sorted(set(tab_fields)), "a field key is listed on more than one tab"
    assert set(tab_fields) == set(form.inputs.keys())
