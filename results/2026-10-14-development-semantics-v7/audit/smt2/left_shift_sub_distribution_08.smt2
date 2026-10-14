(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x120 (bvshl y (_ bv8 32))))
(let ((?x116 (bvshl x (_ bv8 32))))
(let ((?x123 (bvsub ?x116 ?x120)))
(let ((?x24 (bvsub x y)))
(let ((?x122 (bvshl ?x24 (_ bv8 32))))
(and (distinct ?x122 ?x123) true)))))))
(check-sat)
