(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x52 (bvshl y (_ bv0 32))))
(let ((?x49 (bvshl x (_ bv0 32))))
(let ((?x53 (bvadd ?x49 ?x52)))
(let ((?x19 (bvadd x y)))
(let ((?x51 (bvshl ?x19 (_ bv0 32))))
(and (distinct ?x51 ?x53) true)))))))
(check-sat)
