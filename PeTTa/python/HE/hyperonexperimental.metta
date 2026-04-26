!(import! &self pettamorph)

!(petta compileme.metta)
!(petta "(= (h $x) (+ $x 40))")
!(petta (= (j $x) (+ $x 39)))

!(petta (h 2))
!(petta (j 2))
!(petta (fib 10))
