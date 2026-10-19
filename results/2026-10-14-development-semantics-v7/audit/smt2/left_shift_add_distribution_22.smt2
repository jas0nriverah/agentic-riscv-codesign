(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x245 (bvshl y (_ bv22 32))))
(let ((?x241 (bvshl x (_ bv22 32))))
(let ((?x246 (bvadd ?x241 ?x245)))
(let ((?x19 (bvadd x y)))
(let ((?x244 (bvshl ?x19 (_ bv22 32))))
(and (distinct ?x244 ?x246) true)))))))
(check-sat)
