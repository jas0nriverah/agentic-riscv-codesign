(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x85 (bvshl y (_ bv4 32))))
(let ((?x81 (bvshl x (_ bv4 32))))
(let ((?x88 (bvsub ?x81 ?x85)))
(let ((?x24 (bvsub x y)))
(let ((?x87 (bvshl ?x24 (_ bv4 32))))
(and (distinct ?x87 ?x88) true)))))))
(check-sat)
