#import "@preview/cetz:0.5.2": canvas, draw
#let answer = 42
#let proof-drawing() = canvas({
  import draw: *
  circle((0, 0), radius: 1cm, stroke: blue)
})
