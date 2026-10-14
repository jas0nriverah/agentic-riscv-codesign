(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x281 (bvshl y (_ bv26 32))))
(let ((?x277 (bvshl x (_ bv26 32))))
(let ((?x284 (bvsub ?x277 ?x281)))
(let ((?x24 (bvsub x y)))
(let ((?x283 (bvshl ?x24 (_ bv26 32))))
(and (distinct ?x283 ?x284) true)))))))
(check-sat)
