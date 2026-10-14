(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x112 (bvshl y (_ bv7 32))))
(let ((?x108 (bvshl x (_ bv7 32))))
(let ((?x115 (bvsub ?x108 ?x112)))
(let ((?x24 (bvsub x y)))
(let ((?x114 (bvshl ?x24 (_ bv7 32))))
(and (distinct ?x114 ?x115) true)))))))
(check-sat)
