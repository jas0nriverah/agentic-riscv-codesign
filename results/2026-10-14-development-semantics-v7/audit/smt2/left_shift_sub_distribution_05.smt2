(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x94 (bvshl y (_ bv5 32))))
(let ((?x90 (bvshl x (_ bv5 32))))
(let ((?x97 (bvsub ?x90 ?x94)))
(let ((?x24 (bvsub x y)))
(let ((?x96 (bvshl ?x24 (_ bv5 32))))
(and (distinct ?x96 ?x97) true)))))))
(check-sat)
