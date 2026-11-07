class TemplateProvider:
    """Runs the advisor with no LLM: fixed questions, the rules engine's bundle and a template explanation."""

    name = "template"

    def phrase_question(self, field, lang, profile, default):
        return default

    def extract(self, field, content, lang, profile):
        return None

    def choose(self, profile, eligible, suggested):
        return None

    def explain(self, context, lang, default):
        return default
