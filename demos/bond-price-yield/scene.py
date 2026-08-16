from manim import *
from math import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService


def bond_price(y_pct):
    y = y_pct / 100.0
    c = 50.0
    n = 5
    return c * (1 - (1 + y) ** (-n)) / y + 1000.0 * (1 + y) ** (-n)


class GenScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))

        # ---------- 1. Concept Definition ----------
        title = Tex("Bond Price and Yield: An Inverse Relationship")
        title.scale_to_fit_width(config.frame_width * 0.9).to_edge(UP)

        idea = Tex("When yields rise, prices fall. When yields fall, prices rise.")
        idea.scale_to_fit_width(config.frame_width * 0.8).next_to(title, DOWN, buff=0.8)

        with self.voiceover(text="A bond pays fixed cash flows. Its price and its yield always move in opposite directions.") as tracker:
            self.play(Write(title), run_time=tracker.duration)

        with self.voiceover(text="If yields rise, the price falls. If yields fall, the price rises.") as tracker:
            self.play(FadeIn(idea, shift=UP), run_time=tracker.duration)

        self.play(FadeOut(title), FadeOut(idea))

        # ---------- 2. Formula Breakdown ----------
        f_title = Tex("The Pricing Formula").to_edge(UP)
        formula = MathTex(
            r"P = \sum_{t=1}^{n} \frac{C}{(1+y)^{t}} + \frac{F}{(1+y)^{n}}"
        )
        formula.scale_to_fit_width(config.frame_width * 0.7)
        legend = Tex("P is price, C is coupon, F is face value, y is yield")
        legend.scale_to_fit_width(config.frame_width * 0.7).next_to(formula, DOWN, buff=0.9)

        with self.voiceover(text="The price is the present value of every coupon plus the face value, all discounted at the yield.") as tracker:
            self.play(Write(f_title), Write(formula), run_time=tracker.duration)

        with self.voiceover(text="The yield sits in the denominator. A bigger denominator means a smaller present value, so the price must drop.") as tracker:
            self.play(FadeIn(legend), Indicate(formula, color=YELLOW), run_time=tracker.duration)

        self.play(FadeOut(f_title), FadeOut(formula), FadeOut(legend))

        # ---------- 3. Chart ----------
        c_title = Tex("Price versus Yield Curve").to_edge(UP)
        axes = Axes(
            x_range=[1, 11, 2],
            y_range=[700, 1300, 100],
            x_length=8,
            y_length=4.5,
            axis_config={"include_numbers": True, "font_size": 22},
            tips=False,
        )
        labels = VGroup(
            Tex("Yield (percent)").scale(0.6),
            Tex("Price (dollars)").scale(0.6),
        )
        labels[0].next_to(axes.x_axis, DOWN, buff=0.4)
        labels[1].next_to(axes.y_axis, LEFT, buff=0.4).rotate(PI / 2)

        curve = axes.plot(lambda x: bond_price(x), x_range=[1, 11, 0.2], color=BLUE)
        chart = VGroup(axes, labels, curve).scale(0.75).to_edge(DOWN)

        with self.voiceover(text="Plotting price against yield gives a downward sloping curve that bends, or convexity.") as tracker:
            self.play(Create(axes), FadeIn(labels), run_time=tracker.duration)

        with self.voiceover(text="As the yield moves from one percent to eleven percent, the price slides steadily downward.") as tracker:
            self.play(Create(curve), run_time=tracker.duration)

        d1 = Dot(axes.c2p(5, bond_price(5)), color=GREEN).scale(0.9)
        d2 = Dot(axes.c2p(7, bond_price(7)), color=RED).scale(0.9)
        arrow = Arrow(d1.get_center(), d2.get_center(), buff=0.05, color=YELLOW, stroke_width=4)
        marks = VGroup(d1, d2, arrow)
        chart.add(marks)

        with self.voiceover(text="Move the yield from five percent up to seven percent, and the point slides down the curve.") as tracker:
            self.play(FadeIn(d1), FadeIn(d2), GrowArrow(arrow), run_time=tracker.duration)

        self.play(FadeOut(c_title), FadeOut(chart))

        # ---------- 4. Case Study ----------
        case_title = Tex("Case Study: Five Year Bond").to_edge(UP)
        line1 = Tex("Face 1000 dollars, coupon 50 dollars per year, five years").scale(0.7)
        step1 = MathTex(r"y = 5\%: \quad P = 1000.00")
        step2 = MathTex(r"y = 7\%: \quad P = 50 \times 4.1002 + 1000 \times 0.7130")
        step3 = MathTex(r"P = 205.01 + 712.99 = 918.00")
        step4 = MathTex(r"\text{Change} = -82 \text{ dollars}, \; -8.2\%")

        group = VGroup(line1, step1, step2, step3, step4).arrange(DOWN, buff=0.45)
        group.scale_to_fit_width(config.frame_width * 0.8).next_to(case_title, DOWN, buff=0.6)

        with self.voiceover(text="Take a five year bond with a thousand dollar face value paying fifty dollars a year. At a five percent yield it is worth exactly one thousand dollars.") as tracker:
            self.play(Write(case_title), FadeIn(line1), FadeIn(step1), run_time=tracker.duration)

        with self.voiceover(text="Now raise the yield to seven percent. Discount the coupons and the face value at the higher rate.") as tracker:
            self.play(FadeIn(step2), run_time=tracker.duration)

        with self.voiceover(text="The price becomes nine hundred eighteen dollars, a fall of eighty two dollars, or about eight point two percent.") as tracker:
            self.play(FadeIn(step3), FadeIn(step4), run_time=tracker.duration)

        self.play(FadeOut(case_title), FadeOut(group))

        # ---------- 5. Summary ----------
        s_title = Tex("Key Takeaways").to_edge(UP)
        b1 = Tex("1. Yield up means price down, always.")
        b2 = Tex("2. Longer maturity means larger price swings.")
        b3 = Tex("3. The curve is convex, not a straight line.")
        bullets = VGroup(b1, b2, b3).arrange(DOWN, aligned_edge=LEFT, buff=0.5)
        bullets.scale_to_fit_width(config.frame_width * 0.8).next_to(s_title, DOWN, buff=0.7)

        warn = Tex("Remember: a bond priced at par has yield equal to its coupon rate.")
        warn.scale_to_fit_width(config.frame_width * 0.8).next_to(bullets, DOWN, buff=0.7)

        with self.voiceover(text="To summarize: yields up, prices down. Longer bonds swing more, and the relationship is curved, not straight.") as tracker:
            self.play(Write(s_title), FadeIn(bullets, shift=UP), run_time=tracker.duration)

        with self.voiceover(text="One common trap: a bond trades at par only when its yield equals its coupon rate.") as tracker:
            self.play(FadeIn(warn), Indicate(bullets[0], color=YELLOW), run_time=tracker.duration)

        self.wait(1)