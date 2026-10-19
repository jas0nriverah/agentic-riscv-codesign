(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x218 (bvshl y (_ bv19 32))))
(let ((?x214 (bvshl x (_ bv19 32))))
(let ((?x219 (bvadd ?x214 ?x218)))
(let ((?x19 (bvadd x y)))
(let ((?x217 (bvshl ?x19 (_ bv19 32))))
(and (distinct ?x217 ?x219) true)))))))
(check-sat)
