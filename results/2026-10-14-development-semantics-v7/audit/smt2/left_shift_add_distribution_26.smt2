(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x281 (bvshl y (_ bv26 32))))
(let ((?x277 (bvshl x (_ bv26 32))))
(let ((?x282 (bvadd ?x277 ?x281)))
(let ((?x19 (bvadd x y)))
(let ((?x280 (bvshl ?x19 (_ bv26 32))))
(and (distinct ?x280 ?x282) true)))))))
(check-sat)
