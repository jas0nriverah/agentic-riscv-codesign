(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x103 (bvshl y (_ bv6 32))))
(let ((?x99 (bvshl x (_ bv6 32))))
(let ((?x104 (bvadd ?x99 ?x103)))
(let ((?x19 (bvadd x y)))
(let ((?x102 (bvshl ?x19 (_ bv6 32))))
(and (distinct ?x102 ?x104) true)))))))
(check-sat)
