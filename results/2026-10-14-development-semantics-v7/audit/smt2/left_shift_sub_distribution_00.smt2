(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x52 (bvshl y (_ bv0 32))))
(let ((?x49 (bvshl x (_ bv0 32))))
(let ((?x55 (bvsub ?x49 ?x52)))
(let ((?x24 (bvsub x y)))
(let ((?x54 (bvshl ?x24 (_ bv0 32))))
(and (distinct ?x54 ?x55) true)))))))
(check-sat)
