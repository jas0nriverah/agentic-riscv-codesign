(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x60 (bvshl y (_ bv1 32))))
(let ((?x56 (bvshl x (_ bv1 32))))
(let ((?x63 (bvsub ?x56 ?x60)))
(let ((?x24 (bvsub x y)))
(let ((?x62 (bvshl ?x24 (_ bv1 32))))
(and (distinct ?x62 ?x63) true)))))))
(check-sat)
