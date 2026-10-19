(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x60 (bvshl y (_ bv1 32))))
(let ((?x56 (bvshl x (_ bv1 32))))
(let ((?x61 (bvadd ?x56 ?x60)))
(let ((?x19 (bvadd x y)))
(let ((?x59 (bvshl ?x19 (_ bv1 32))))
(and (distinct ?x59 ?x61) true)))))))
(check-sat)
