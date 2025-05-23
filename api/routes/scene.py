from manim import *

class GenScene(Scene):
    def construct(self):
        title = Text("Two-Stage DCF Model to Calculate Intrinsic Value", font_size=36).to_edge(UP)
        self.play(Write(title))

        stage1 = Text("Stage 1: Forecast Free Cash Flows (FCF) during High Growth Period", font_size=24).next_to(title, DOWN, buff=0.5)
        self.play(Write(stage1))

        fcf_formula = MathTex(
            "FCF_t = FCF_0 \\times (1 + g)^t",
            " \\quad \\text{for } t = 1, 2, ..., n"
        ).next_to(stage1, DOWN, buff=0.5)
        self.play(Write(fcf_formula))

        stage2 = Text("Stage 2: Calculate Terminal Value using Perpetuity Growth Model", font_size=24).next_to(fcf_formula, DOWN, buff=1)
        self.play(Write(stage2))

        terminal_value = MathTex(
            "TV_n = \\frac{FCF_{n+1}}{r - g_{LT}}",
            "\\quad \\text{where } FCF_{n+1} = FCF_n \\times (1 + g_{LT})"
        ).next_to(stage2, DOWN, buff=0.5)
        self.play(Write(terminal_value))

        discounting = Text("Discount FCFs and Terminal Value to Present Value", font_size=24).next_to(terminal_value, DOWN, buff=1)
        self.play(Write(discounting))

        pv_formula = MathTex(
            "Intrinsic\\ Value = \\sum_{t=1}^n \\frac{FCF_t}{(1+r)^t} + \\frac{TV_n}{(1+r)^n}"
        ).next_to(discounting, DOWN, buff=0.5)
        self.play(Write(pv_formula))