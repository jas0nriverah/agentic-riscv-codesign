(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x112 (bvshl y (_ bv7 32))))
(let ((?x108 (bvshl x (_ bv7 32))))
(let ((?x113 (bvadd ?x108 ?x112)))
(let ((?x19 (bvadd x y)))
(let ((?x111 (bvshl ?x19 (_ bv7 32))))
(and (distinct ?x111 ?x113) true)))))))
(check-sat)
