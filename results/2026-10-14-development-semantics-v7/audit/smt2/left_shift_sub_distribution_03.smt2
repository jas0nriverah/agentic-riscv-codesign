(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x77 (bvshl y (_ bv3 32))))
(let ((?x73 (bvshl x (_ bv3 32))))
(let ((?x80 (bvsub ?x73 ?x77)))
(let ((?x24 (bvsub x y)))
(let ((?x79 (bvshl ?x24 (_ bv3 32))))
(and (distinct ?x79 ?x80) true)))))))
(check-sat)
