(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x317 (bvshl y (_ bv30 32))))
(let ((?x313 (bvshl x (_ bv30 32))))
(let ((?x318 (bvadd ?x313 ?x317)))
(let ((?x19 (bvadd x y)))
(let ((?x316 (bvshl ?x19 (_ bv30 32))))
(and (distinct ?x316 ?x318) true)))))))
(check-sat)
