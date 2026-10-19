(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x103 (bvshl y (_ bv6 32))))
(let ((?x99 (bvshl x (_ bv6 32))))
(let ((?x106 (bvsub ?x99 ?x103)))
(let ((?x24 (bvsub x y)))
(let ((?x105 (bvshl ?x24 (_ bv6 32))))
(and (distinct ?x105 ?x106) true)))))))
(check-sat)
