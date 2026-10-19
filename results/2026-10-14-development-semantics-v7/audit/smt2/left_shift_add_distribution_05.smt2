(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x94 (bvshl y (_ bv5 32))))
(let ((?x90 (bvshl x (_ bv5 32))))
(let ((?x95 (bvadd ?x90 ?x94)))
(let ((?x19 (bvadd x y)))
(let ((?x93 (bvshl ?x19 (_ bv5 32))))
(and (distinct ?x93 ?x95) true)))))))
(check-sat)
