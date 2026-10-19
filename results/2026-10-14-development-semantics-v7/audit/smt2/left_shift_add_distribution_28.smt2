(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x299 (bvshl y (_ bv28 32))))
(let ((?x295 (bvshl x (_ bv28 32))))
(let ((?x300 (bvadd ?x295 ?x299)))
(let ((?x19 (bvadd x y)))
(let ((?x298 (bvshl ?x19 (_ bv28 32))))
(and (distinct ?x298 ?x300) true)))))))
(check-sat)
