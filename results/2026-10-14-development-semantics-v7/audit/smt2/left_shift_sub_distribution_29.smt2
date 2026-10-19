(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x308 (bvshl y (_ bv29 32))))
(let ((?x304 (bvshl x (_ bv29 32))))
(let ((?x311 (bvsub ?x304 ?x308)))
(let ((?x24 (bvsub x y)))
(let ((?x310 (bvshl ?x24 (_ bv29 32))))
(and (distinct ?x310 ?x311) true)))))))
(check-sat)
